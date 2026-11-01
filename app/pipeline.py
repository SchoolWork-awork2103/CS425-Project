"""Local conversation orchestration. Components are injectable for asset-free tests."""
import logging
import threading
import time

from dialogue.catalogue import ROOT, TraitCatalogue
from dialogue.interpreter import NLUInterpreter, QwenInterpreter
from dialogue.manager import DialogueManager
from dialogue.types import InterpretationError, PoemRecord
from .model_service import SharedModelService
from .device import validate_device

log = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, cfg=None, system="D", device="cpu", *, catalogue=None, interpreter=None,
                 service=None, planner=None, reranker=None, generator_a=None):
        if cfg is None:
            from utils import load_config
            cfg = load_config()
        if system not in {"A", "D"}:
            raise ValueError("Generator must be A or D")
        validate_device(device)
        self.cfg, self.system, self.device = cfg, system, device
        self.catalogue = catalogue or TraitCatalogue.load(ROOT / cfg["paths"].get("trait_catalogue", "data/trait_catalogue.json"))
        options = cfg.get("dialogue", {})
        self.manager = DialogueManager(self.catalogue, options.get("history_limit", 20),
                                       options.get("default_intensity", "mild"))
        self.service = service if service is not None else SharedModelService(cfg, device)
        self.interpreter = interpreter
        self.planner, self.reranker, self.generator_a = planner, reranker, generator_a
        self._lock = threading.RLock()
        self.last_trace = {}

    def _interpreter(self):
        if self.interpreter is None:
            options = self.cfg.get("dialogue", {})
            if options.get("backend", "qwen") == "nlu":
                from nlu.joint_model import NLU
                from nlu.normalize import TraitNormalizer
                normalizer = TraitNormalizer(self.cfg, local_files_only=options.get("local_files_only", True))
                nlu = NLU.load(ROOT / self.cfg["paths"]["checkpoints"] / "nlu_joint_best",
                               self.device, normalizer)
                self.interpreter = NLUInterpreter(nlu, self.catalogue)
            elif options.get("backend", "qwen") == "qwen":
                self.interpreter = QwenInterpreter(
                    self.service, self.catalogue, options.get("validation_retries", 1),
                    options.get("max_input_tokens", 4096), options.get("max_new_tokens", 384))
            else:
                raise ValueError("dialogue.backend must be qwen or nlu")
        return self.interpreter

    def _planner(self):
        if self.planner is None:
            from phonetics.planner import RhymePlanner
            self.planner = RhymePlanner(self.cfg)
        return self.planner

    def _reranker(self):
        if self.reranker is None:
            from reranker.rerank import Reranker
            from reranker.trait_fit import TraitFit
            fit = TraitFit.load(ROOT / self.cfg["paths"]["checkpoints"] / "trait_fit_best", self.device)
            self.reranker = Reranker(self.cfg, trait_fit=fit)
        return self.reranker

    def _generate(self, system, traits, intensity, end_words):
        kwargs = self.cfg.get("sampling", {"temperature": 0.8, "top_p": 0.9, "rep_penalty": 1.2}).copy()
        kwargs["n"] = self.cfg["reranker"]["tuning"]["per_plan"]
        if system == "D":
            return self.service.generate(traits, intensity, end_words, **kwargs)
        if self.generator_a is None:
            from generation.gru_lm import load_generator, generate
            checkpoint = ROOT / self.cfg["paths"]["checkpoints"] / self.cfg["reranker"]["tuning"]["checkpoints"]["A"]
            if not checkpoint.is_file():
                raise FileNotFoundError(f"Missing System A checkpoint: {checkpoint}")
            model, codec = load_generator(checkpoint, self.cfg, self.device)
            self.generator_a = lambda ts, intensity, ends, **kw: generate(model, codec, ts, intensity, ends, device=self.device, **kw)
        return self.generator_a(traits, intensity, end_words, **kwargs)

    def respond(self, message, state=None, system=None):
        with self._lock:
            start = time.perf_counter()
            self.last_trace = {"stage": "control", "system": system or self.system}
            state = state if state is not None else self.manager.initial_state()
            try:
                reply, new_state = self._respond(message, state, system or self.system)
            finally:
                self.last_trace["total_seconds"] = time.perf_counter() - start
            return reply, new_state

    def _respond(self, message, state, system):
        if system not in {"A", "D"}:
            raise ValueError("Generator must be A or D")
        control = self.manager.control(message, state)
        if control:
            decision, state = control
            self.last_trace["decision"] = decision.kind
            return decision.text, state
        try:
            self.last_trace["stage"] = "interpretation"
            start = time.perf_counter()
            turn = self._interpreter().interpret(message, state)
            self.last_trace.update(interpretation_seconds=time.perf_counter() - start,
                                   interpretation=turn.to_dict(),
                                   attempts=getattr(self.interpreter, "last_attempts", 1))
            self.last_trace["stage"] = "policy"
            decision, new_state = self.manager.step(turn, state)
        except InterpretationError:
            self.last_trace["attempts"] = getattr(self.interpreter, "last_attempts", 0)
            self.last_trace["error"] = "invalid_interpretation"
            return "I couldn't interpret that clearly. Please give a shorter request with traits and mild or harsh intensity.", state
        except (OSError, RuntimeError, ValueError, ImportError):
            log.exception("Dialogue interpretation failed")
            self.last_trace["error"] = "interpretation_unavailable"
            return "The interpreter is unavailable. Check the local model setup in README.md and try again.", state
        self.last_trace["decision"] = decision.kind
        if decision.kind != "generate":
            return decision.text, new_state
        try:
            self.last_trace["stage"] = "planning"
            k = self.cfg["reranker"]["tuning"]["plans"]
            planner = self._planner()
            plans = planner.plan(decision.traits, k=k, exclude=new_state.last_plan or ())
            if not plans and new_state.last_plan:
                alternatives = planner.plan(decision.traits, k=k + 1)
                fresh = [p for p in alternatives if p["end_words"] != new_state.last_plan]
                plans = (fresh or alternatives)[:k]
            if not plans:
                raise ValueError("No rhyme plans available")
            retries = self.cfg.get("dialogue", {}).get("generation_retries", 1)
            if not 0 <= retries <= 2:
                raise ValueError("Generation retries must be between 0 and 2")
            for attempt in range(retries + 1):
                self.last_trace["stage"] = "generation"
                candidates = []
                for plan in plans:
                    batch = self._generate(system, decision.traits, decision.intensity, plan["end_words"])
                    candidates.extend({**c, "planned_end_words": list(plan["end_words"]), "system": system} for c in batch)
                self.last_trace["stage"] = "selection"
                ranked = self._reranker().rank(decision.traits, candidates, new_state.history)
                self.last_trace.update(generation_batches=attempt + 1, candidates=len(candidates), survivors=len(ranked))
                if ranked:
                    best = ranked[0]
                    from phonetics import last_word, aabb_score
                    # Check the externally supplied reranker result at the output boundary too.
                    lines = best["lines"]
                    if len(lines) != 4 or any(not l.strip() or "\n" in l for l in lines) or aabb_score(lines) != 1.0:
                        raise ValueError("Selected poem violates the four-line AABB contract")
                    poem = PoemRecord(list(lines), system, list(decision.traits), decision.intensity,
                                      best["planned_end_words"], [last_word(l) for l in lines],
                                      {"score": best.get("score"), "features": best.get("features", {})})
                    self.last_trace["stage"] = "complete"
                    return "\n".join(lines), self.manager.record_success(new_state, poem)
            self.last_trace["error"] = "no_valid_candidate"
        except (OSError, RuntimeError, ValueError, ImportError):
            log.exception("Poem generation failed at %s", self.last_trace["stage"])
            self.last_trace["error"] = "generation_unavailable"
        return "I couldn't find a fresh valid AABB roast. Your settings are saved; try another one or change the traits.", new_state
