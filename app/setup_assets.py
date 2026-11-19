"""Check local project assets; --download fetches whatever is missing.

--download takes the trained checkpoints (NLU, trait-fit, Systems A, D and E) from the
team's Hugging Face repo (paths.checkpoints_repo), skipping any already in checkpoints/,
then the public base models, Detoxify and GloVe (derived from glove.6B.zip).
No inference is run here.
"""
import argparse
import json
from pathlib import Path

from dialogue.catalogue import ROOT
from utils import load_config

GLOVE_ZIP_URL = "https://huggingface.co/stanfordnlp/glove/resolve/main/glove.6B.zip"
GLOVE_ZIP_SHA256 = "6471382cdd837544bf3ac72497a38715e845897d265b2b424b4761832009c837"
# Detoxify("original") loads this through torch.hub, so it is cached where torch.hub keeps checkpoints
DETOXIFY_URL = "https://github.com/unitaryai/detoxify/releases/download/v0.1-alpha/toxic_original-c1212f89.ckpt"
# The Qwen base files the app needs (no README, LICENSE, .gitattributes)
QWEN_PATTERNS = ["*.json", "*.safetensors", "*.txt", "*.model", "*.tiktoken"]


def detoxify_checkpoint():
    import torch
    return Path(torch.hub.get_dir()) / "checkpoints" / DETOXIFY_URL.rsplit("/", 1)[1]


def check(cfg):
    checkpoints = ROOT / cfg["paths"]["checkpoints"]
    required = {"Qwen poem adapter": checkpoints / cfg["reranker"]["tuning"]["checkpoints"]["D"] / "adapter_config.json",
                "trait-fit classifier": checkpoints / "trait_fit_best" / "config.json",
                "Detoxify weights": detoxify_checkpoint(),
                "GloVe vectors": Path(str(ROOT / cfg["paths"]["glove"]) + ".npy"),
                "GloVe vocabulary": Path(str(ROOT / cfg["paths"]["glove"]) + ".vocab.txt")}
    if cfg["dialogue"]["backend"] == "nlu":
        required["NLU model"] = checkpoints / "nlu_joint_best" / "model.pt"
    results = {name: {"path": str(path), "present": path.is_file()} for name, path in required.items()}
    fit = checkpoints / "trait_fit_best"
    for name in ("trait_fit.json", "tokenizer_config.json"):
        results["trait-fit " + name] = {"path": str(fit / name), "present": (fit / name).is_file()}
    results["trait-fit classifier weights"] = {
        "present": any((fit / name).is_file() for name in ("model.safetensors", "pytorch_model.bin"))}
    try:
        from transformers import AutoConfig, AutoTokenizer
        for name in ("Qwen/Qwen2.5-1.5B-Instruct", "bert-base-uncased"):
            try:
                AutoConfig.from_pretrained(name, local_files_only=True)
                AutoTokenizer.from_pretrained(name, local_files_only=True)
                results[name + " config/tokenizer"] = {"present": True}
            except (OSError, ValueError):
                results[name + " config/tokenizer"] = {"present": False}
        from huggingface_hub import snapshot_download
        try:
            # Same patterns as download(): newer huggingface_hub rejects a partial snapshot without them
            snapshot = Path(snapshot_download("Qwen/Qwen2.5-1.5B-Instruct", local_files_only=True,
                                              allow_patterns=QWEN_PATTERNS))
            index = snapshot / "model.safetensors.index.json"
            if index.is_file():
                shards = set(json.loads(index.read_text(encoding="utf-8"))["weight_map"].values())
                weights_present = bool(shards) and all((snapshot / shard).is_file() for shard in shards)
            else:
                weights_present = (snapshot / "model.safetensors").is_file()
            results["Qwen base weights"] = {"present": weights_present}
        except OSError:
            results["Qwen base weights"] = {"present": False}
    except ImportError:
        results["runtime dependencies"] = {"present": False}
    # All three generators are in the UI dropdown, so each one's checkpoint is required.
    results["System A checkpoint"] = {
        "path": str(checkpoints / cfg["reranker"]["tuning"]["checkpoints"]["A"]),
        "present": (checkpoints / cfg["reranker"]["tuning"]["checkpoints"]["A"]).is_file()}
    results["System E checkpoint"] = {
        "path": str(checkpoints / cfg["gpt2"]["checkpoint"]),
        "present": (checkpoints / cfg["gpt2"]["checkpoint"] / "model.safetensors").is_file()}
    return results


def _trained_checkpoints(cfg, backend):
    """{pattern in the team's Hugging Face repo: local file that shows it is already there}."""
    checkpoints = ROOT / cfg["paths"]["checkpoints"]
    a, d = cfg["reranker"]["tuning"]["checkpoints"]["A"], cfg["reranker"]["tuning"]["checkpoints"]["D"]
    e = cfg["gpt2"]["checkpoint"]
    wanted = {a: checkpoints / a,
              f"{d}/*": checkpoints / d / "adapter_model.safetensors",
              f"{e}/*": checkpoints / e / "model.safetensors",
              "trait_fit_best/*": checkpoints / "trait_fit_best" / "model.safetensors"}
    if backend == "nlu":
        wanted["nlu_joint_best/*"] = checkpoints / "nlu_joint_best" / "model.pt"
    return wanted


def download(cfg, backend):
    from huggingface_hub import snapshot_download
    # Trained checkpoints from the team's repo, only the ones missing locally, so local copies are never replaced.
    missing = [pattern for pattern, marker in _trained_checkpoints(cfg, backend).items() if not marker.is_file()]
    if missing:
        print("Downloading trained checkpoints:", ", ".join(missing))
        snapshot_download(cfg["paths"]["checkpoints_repo"], local_dir=ROOT / cfg["paths"]["checkpoints"],
                          allow_patterns=missing)
    # Public base models and data
    snapshot_download("Qwen/Qwen2.5-1.5B-Instruct", allow_patterns=QWEN_PATTERNS)
    snapshot_download("bert-base-uncased", allow_patterns=["*.json", "*.txt"])
    if backend == "nlu":
        snapshot_download(cfg["nlu"]["span_encoder"])
    target = detoxify_checkpoint()
    if not target.exists():
        import torch
        target.parent.mkdir(parents=True, exist_ok=True)
        torch.hub.download_url_to_file(DETOXIFY_URL, str(target), hash_prefix="c1212f89")
    _download_glove(cfg)


def _download_glove(cfg):
    """Fetch the public GloVe 6B zip and derive the compact vectors (skipped if already present)."""
    base = str(ROOT / cfg["paths"]["glove"])
    if Path(base + ".npy").is_file() and Path(base + ".vocab.txt").is_file():
        return
    import importlib.util
    import tempfile

    import torch

    spec = importlib.util.spec_from_file_location("prepare_glove", ROOT / "data" / "prepare_glove.py")
    prepare_glove = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare_glove)
    Path(base).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "glove.6B.zip"
        torch.hub.download_url_to_file(GLOVE_ZIP_URL, str(zip_path), hash_prefix=GLOVE_ZIP_SHA256)
        prepare_glove.prepare(str(zip_path), Path(base))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--backend", choices=["qwen", "nlu"], default=None, help="default: dialogue.backend")
    args = parser.parse_args()
    cfg = load_config()
    backend = cfg["dialogue"]["backend"] = args.backend or cfg["dialogue"]["backend"]
    if args.download:
        download(cfg, backend)
    results = check(cfg)
    print(json.dumps(results, indent=2))
    if any(not r["present"] for r in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
