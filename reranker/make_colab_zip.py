"""Packs what reranker/train_trait_fit.ipynb needs on Colab into reranker_colab.zip at the project root, to upload by
hand: the reranker code, utils.py, config.yaml, traits.json, the diss corpus, the reranker negatives, and
prepare_negatives.py with form_checks.py (the CLOSE trait groups used to build the wrong_trait negatives).

Run from the project root:  python reranker/make_colab_zip.py
"""
import sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["utils.py", "config.yaml", "data/traits.json", "data/form_checks.py", "data/negatives/prepare_negatives.py",
         "reranker/__init__.py", "reranker/trait_fit.py", "reranker/train_trait_fit.py",
         "data/disses/corpus/train.jsonl", "data/disses/corpus/val.jsonl", "data/disses/corpus/test.jsonl",
         "data/negatives/corpus/negatives.jsonl"]


def main():
    missing = [f for f in FILES if not (ROOT / f).exists()]
    if missing:
        sys.exit(f"missing: {missing} (run data/disses/prepare_disses.py and data/negatives/prepare_negatives.py first)")
    out = ROOT / "reranker_colab.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(ROOT / f, f)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(FILES)} files): upload it in the notebook's first cell")


if __name__ == "__main__":
    main()
