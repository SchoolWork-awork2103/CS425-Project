"""Evaluate gold policy, actual interpretation, or the integrated local application.

python -m eval.run_dialogue_eval --mode policy
python -m eval.run_dialogue_eval --mode interpreter --backend qwen --device cuda
python -m eval.run_dialogue_eval --mode integrated --backend qwen --system D --device cuda
"""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import sys
import time

from app.pipeline import Pipeline
from dialogue.catalogue import ROOT
from dialogue.prompts import PROMPT_VERSION
from dialogue.types import InterpretationError, PoemRecord, TurnInterpretation
from utils import load_config


def file_hash(path):
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentile(values, fraction):
    if not values:
        return None
    return sorted(values)[min(len(values) - 1, int((len(values) - 1) * fraction))]


def peak_process_memory():
    if sys.platform == "win32":
        import psutil
        return psutil.Process().memory_info().peak_wset
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def run(fixtures, mode="policy", backend="qwen", system="D", device="cpu", cfg=None):
    cfg = cfg or load_config()
    cfg["dialogue"]["backend"] = backend
    pipeline = Pipeline(cfg, system, device)
    conversations = [json.loads(line) for line in Path(fixtures).read_text(encoding="utf-8").splitlines() if line.strip()]
    counts, details, times, interpretation_times = Counter(), [], [], []
    if mode != "policy":
        import torch
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
    for conversation in conversations:
        state, complete = pipeline.manager.initial_state(), True
        for number, row in enumerate(conversation["turns"], 1):
            start = time.perf_counter()
            predicted, decision, error, attempts = None, None, None, 0
            try:
                if mode == "integrated":
                    _, state = pipeline.respond(row["message"], state, system)
                    trace = pipeline.last_trace
                    decision, error = trace.get("decision"), trace.get("error")
                    predicted, attempts = trace.get("interpretation"), trace.get("attempts", 0)
                    if "interpretation_seconds" in trace:
                        interpretation_times.append(trace["interpretation_seconds"])
                else:
                    control = pipeline.manager.control(row["message"], state)
                    if control:
                        action, state = control
                    else:
                        if mode == "policy":
                            turn = TurnInterpretation.from_dict(row["gold"], pipeline.catalogue.keys)
                        else:
                            interpreter = pipeline._interpreter()
                            infer_start = time.perf_counter()
                            turn = interpreter.interpret(row["message"], state)
                            interpretation_times.append(time.perf_counter() - infer_start)
                            attempts = interpreter.last_attempts
                        predicted = turn.to_dict()
                        action, state = pipeline.manager.step(turn, state)
                    decision = action.kind
                    if decision == "generate" and mode == "policy":
                        # Explicit mocked result: tests policy bookkeeping, not poem quality.
                        state = pipeline.manager.record_success(state, PoemRecord(
                            ["mock poem"] * 4, system, list(state.traits), state.intensity, ["mock"] * 4, ["mock"] * 4))
            except (InterpretationError, OSError, RuntimeError, ValueError, ImportError) as exc:
                error = type(exc).__name__
                if mode == "interpreter" and pipeline.interpreter is not None:
                    attempts = pipeline.interpreter.last_attempts
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            expected = row["expect"]
            correct = (state.traits == expected["traits"] and state.intensity == expected["intensity"]
                       and decision == expected["decision"] and bool(state.awaiting) == expected["pending"]
                       and state.generic == expected.get("generic", False) and error is None)
            if mode == "integrated" and expected["decision"] == "generate":
                correct = correct and bool(state.history) and pipeline.last_trace.get("stage") == "complete"
            counts["turns"] += 1
            counts["state_correct"] += correct
            counts["clarifications"] += decision == "clarify"
            counts["errors"] += error is not None
            counts["retried"] += attempts > 1
            if mode != "policy" and attempts:
                counts["interpretation_calls"] += 1
                counts["valid_first_attempt"] += predicted is not None and attempts == 1
                counts["valid_after_retry"] += predicted is not None
            if mode != "policy" and predicted is not None and row.get("gold"):
                gold = row["gold"]
                counts["interpreted"] += 1
                counts["complete_interpretation_correct"] += predicted == gold
                counts["intensity_correct"] += predicted["intensity"] == gold["intensity"]
                counts["operation_correct"] += predicted["trait_updates"] == gold["trait_updates"]
                def keys(data):
                    return {t for u in data["trait_updates"] if u["mode"] != "remove" for t in u["traits"]}
                counts["trait_set_correct"] += keys(predicted) == keys(gold)
                if gold["unresolved"] and all(not u["candidates"] and u["target"] == "traits" for u in gold["unresolved"]):
                    counts["unsupported_turns"] += 1
                    counts["unsupported_false_match"] += bool(keys(predicted)) and not predicted["unresolved"]
            complete = complete and correct
            details.append({"conversation": conversation["id"], "turn": number, "correct": correct,
                            "state": state.summary(), "decision": decision, "prediction": predicted,
                            "error": error, "stage": pipeline.last_trace.get("stage") if mode == "integrated" else mode,
                            "seconds": elapsed, "attempts": attempts})
        counts["conversations"] += 1
        counts["conversations_complete"] += complete
    versions = {}
    for name in ("torch", "transformers", "peft", "gradio", "detoxify"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    memory = None
    gpu = None
    if mode != "policy":
        import torch
        if device == "cuda":
            memory, gpu = torch.cuda.max_memory_allocated(), torch.cuda.get_device_name()
    adapter = ROOT / cfg["paths"]["checkpoints"] / cfg["reranker"]["tuning"]["checkpoints"]["D"]
    adapter_cfg = adapter / "adapter_config.json"
    weights = adapter / "adapter_model.safetensors"
    if not weights.is_file():
        weights = adapter / "adapter_model.bin"
    return {"mode": mode, "backend": backend, "system": system,
            "model_inference_run": mode != "policy" and counts["interpreted"] > 0, "prompt_version": PROMPT_VERSION,
            "fixture_sha256": hashlib.sha256(Path(fixtures).read_bytes()).hexdigest(),
            "catalogue_sha256": pipeline.catalogue.fingerprint,
            "checkpoint": str(adapter), "adapter_config_sha256": file_hash(adapter_cfg),
            "adapter_weights_sha256": file_hash(weights),
            "settings": {"dialogue": cfg["dialogue"], "sampling": cfg.get("sampling"), "reranker": cfg["reranker"]},
            "hardware": {"platform": platform.platform(), "processor": platform.processor(), "device": device, "gpu": gpu},
            "versions": versions, "counts": dict(counts),
            "state_accuracy": counts["state_correct"] / max(counts["turns"], 1),
            "conversation_completion": counts["conversations_complete"] / max(counts["conversations"], 1),
            "latency_seconds": {"median": statistics.median(times) if times else None, "p95": percentile(times, 0.95)},
            "interpretation_seconds": {"median": statistics.median(interpretation_times) if interpretation_times else None,
                                       "p95": percentile(interpretation_times, 0.95)},
            "peak_cuda_memory_bytes": memory, "peak_process_memory_bytes": peak_process_memory(),
            "details": details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["policy", "interpreter", "integrated"], default="policy")
    parser.add_argument("--backend", choices=["qwen", "nlu"], default="qwen")
    parser.add_argument("--system", choices=["A", "D"], default="D")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--fixtures", type=Path, default=ROOT / "eval/dialogue_test.jsonl")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = run(args.fixtures, args.mode, args.backend, args.system, args.device)
    output = args.output or ROOT / f"eval/results/dialogue/{args.mode}_{args.backend}_{args.system}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "state_accuracy": result["state_accuracy"],
                      "conversation_completion": result["conversation_completion"], "counts": result["counts"]}))
    if result["counts"].get("errors") or (args.mode == "policy" and result["state_accuracy"] < 1):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
