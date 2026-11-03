"""Local conversation orchestration. Components are injectable for asset-free tests."""
import difflib
import logging
import re
import threading
import time

from dialogue.catalogue import ROOT, TraitCatalogue
from dialogue.interpreter import NLUInterpreter, QwenInterpreter
from dialogue.manager import DialogueManager
from dialogue.types import InterpretationError, PoemRecord, TraitUpdate
from .model_service import SharedModelService
from .device import validate_device

log = logging.getLogger(__name__)

# "Roast" only ever refers to the generated poem in this app. If the interpreter drops an
# explicit roast request, the policy still requires it to generate; explicit refusals keep the no-op.
ROAST_REQUEST = re.compile(r"\broast(?:ed|s|ing)?\b", re.IGNORECASE)
# A denial cue anywhere in the few words before "roast(s|ed|ing)" keeps the safety net silent.
# Missing a refusal roasts the user against their words, while a false refusal only withholds
# this fallback - the interpreter's own request_generation flag still generates - so the
# pattern is deliberately generous. Apostrophes arrive as ASCII or typographic (’).
_REFUSAL = (r"cannot|can ?not|can['\u2019]?t|ca['\u2019]?n?t|won['\u2019]?t|wont|wouldn['\u2019]?t"
            r"|couldn['\u2019]?t|don['\u2019]?t|do not|doesn['\u2019]?t|does not|didn['\u2019]?t|did not"
            r"|never|no|not|without|stop|quit|cease|avoid|refus(?:e|es|ed)|declin(?:e|es|ed)|skip")
ROAST_REFUSAL = re.compile(rf"\b(?:{_REFUSAL})\b(?:\s+\w+){{0,4}}\s+roast(?:s|ed|ing)?\b", re.IGNORECASE)

# Obvious synonyms of the two real intensity values, accepted when the model outputs the
# word the user actually used.
INTENSITY_ALIASES = {"high": "harsh", "strong": "harsh", "meaner": "harsh",
                     "low": "mild", "soft": "mild", "gentle": "mild", "softer": "mild"}

# A bare continuation request cannot describe a trait by construction, but the small
# model sometimes answers one by inventing an add ("another" -> add outgoing), which
# silently rewrites the user's settings before an un-echoed generate reply.
BARE_CONTINUATION = re.compile(
    r"\A(?:another(?:\s+one(?:\s+roast)?)?|another\s+roast|one\s+more(?:\s+roast)?|next(?:\s+one)?|again"
    r"|(?:give|write)\s+me\s+another|more(?:\s+of\s+(?:that|those))?|keep\s+going)\s*[.!?,]*\Z", re.IGNORECASE)


def _trait_mentioned(key, message, catalogue):
    """True when the message names or approximates the trait: the key, a synonym
    (whole or one content word of a multi-word synonym), or a near-typo."""
    low = message.casefold().replace("-", " ")
    words = {w for w in re.findall(r"[a-z0-9']+", low) if len(w) >= 3}
    for form in (key, *catalogue.entries[key]["synonyms"]):
        form = form.casefold().replace("-", " ")
        if form in low:
            return True
        for part in form.split():
            if part in words:
                return True
            if len(part) >= 4 and any(difflib.SequenceMatcher(None, part, w).ratio() >= 0.70
                                       for w in words):
                return True
    return False


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
            backend = options.get("backend", "nlu")
            if backend == "nlu":
                from nlu.joint_model import NLU
                from nlu.normalize import TraitNormalizer
                normalizer = TraitNormalizer(self.cfg, local_files_only=options.get("local_files_only", True))
                nlu = NLU.load(ROOT / self.cfg["paths"]["checkpoints"] / "nlu_joint_best",
                               self.device, normalizer)
                self.interpreter = NLUInterpreter(nlu, self.catalogue)
            elif backend == "qwen":
                self.interpreter = QwenInterpreter(
                    self.service, self.catalogue, options.get("validation_retries", 1),
                    options.get("max_input_tokens", 4096), options.get("max_new_tokens", 384),
                    intensity_aliases=INTENSITY_ALIASES)
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
            self.reranker = Reranker(self.cfg, device=self.device)
        return self.reranker

    def _select(self, ranked, last_batch):
        """The reply among the reranked candidates. With dialogue.require_aabb, the best full-AABB one; on the last
        generation batch, the best of any rhyme if none is (the reranker's aabb weight has already ranked them)."""
        if not self.cfg.get("dialogue", {}).get("require_aabb", True):
            return ranked[0] if ranked else None
        full = [c for c in ranked if c["features"]["aabb"] == 1.0]
        if full:
            return full[0]
        if last_batch and ranked:
            self.last_trace["aabb_fallback"] = True
            return ranked[0]
        return None

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

    def _ground_destructive_updates(self, turn, message, state):
        """Drop remove/replace edits the message never asks for.

        The small model sometimes echoes session state back as operations
        ("change intensity to harsh" -> remove confident), which silently
        corrupts the user's settings. Every trait in a destructive edit must
        therefore be named or approximated by the message itself. Add
        operations are left to the model (they show in the settings reply),
        and an answer to a pending question may describe rather than name the
        trait.
        """
        if turn.kind == "answer" and state.awaiting is not None:
            return
        kept, dropped = [], []
        for update in turn.trait_updates:
            if update.mode == "replace" and not update.traits:
                # An empty replacement would silently clear every trait.
                dropped.append(update)
            elif update.mode in {"remove", "replace"}:
                grounded = [t for t in update.traits if _trait_mentioned(t, message, self.catalogue)]
                if grounded == update.traits:
                    kept.append(update)
                elif update.mode == "remove" and grounded:
                    kept.append(TraitUpdate("remove", grounded))
                else:
                    dropped.append(update)
            else:
                kept.append(update)
        if dropped:
            turn.trait_updates = kept
            self.last_trace["ungrounded_updates_dropped"] = [
                {"mode": u.mode, "traits": list(u.traits)} for u in dropped]

    def respond(self, message, state=None, system=None):
        with self._lock:
            start = time.perf_counter()
            self.last_trace = {"stage": "control", "system": system or self.system}
            message = "" if message is None else str(message)
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
                                   attempts=getattr(self.interpreter, "last_attempts", 1),
                                   **({"interpretation_salvaged": True}
                                       if getattr(self.interpreter, "last_salvaged", False) else {}))
            notes = getattr(self.interpreter, "last_notes", [])
            if isinstance(notes, list) and notes:
                self.last_trace["notes"] = list(notes)
            if (turn.kind in {"request", "answer"} and not turn.request_generation
                    and not turn.generic_requested
                    and ROAST_REQUEST.search(message) and not ROAST_REFUSAL.search(message)):
                # The trace above keeps the model's raw output; the policy requires an
                # explicit roast request to generate, so restore the dropped flag here.
                turn.request_generation = True
                self.last_trace["roast_request_restored"] = True
            if BARE_CONTINUATION.match(message.strip()) and (turn.trait_updates or turn.generic_requested):
                # A bare continuation keeps the settings; nothing it says can change them.
                self.last_trace["bare_continuation_updates_dropped"] = [
                    {"mode": u.mode, "traits": list(u.traits)} for u in turn.trait_updates]
                turn.trait_updates = []
                turn.generic_requested = False
            self._ground_destructive_updates(turn, message, state)
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
                ranked = self._reranker().rerank(decision.traits, candidates, new_state.history)
                self.last_trace.update(generation_batches=attempt + 1, candidates=len(candidates), survivors=len(ranked))
                best = self._select(ranked, attempt == retries)
                if best:
                    from phonetics import last_word
                    lines = best["lines"]
                    if len(lines) != 4 or any(not l.strip() or "\n" in l for l in lines):
                        raise ValueError("Selected poem is not four lines")
                    poem = PoemRecord(list(lines), system, list(decision.traits), decision.intensity,
                                      best["planned_end_words"], [last_word(l) for l in lines],
                                      {"score": best.get("score"), "features": best.get("features", {})})
                    self.last_trace["stage"] = "complete"
                    # "Unknown trait: use the nearest trait and say so" (pipeline.md, Phase 7).
                    notes = self.last_trace.get("notes", [])
                    return "\n".join([*notes, *lines]), self.manager.record_success(new_state, poem)
            self.last_trace["error"] = "no_valid_candidate"
        except (OSError, RuntimeError, ValueError, ImportError):
            log.exception("Poem generation failed at %s", self.last_trace["stage"])
            self.last_trace["error"] = "generation_unavailable"
        return "I couldn't find a fresh valid AABB roast. Your settings are saved; try another one or change the traits.", new_state
