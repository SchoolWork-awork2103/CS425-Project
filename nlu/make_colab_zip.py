"""Packs what nlu/train_nlu.ipynb needs on Colab into nlu_colab.zip at the project root, to upload by hand: the nlu
code, utils.py, config.yaml, traits.json, the NLU corpus, and prepare_negatives.py with form_checks.py (the CLOSE
trait groups used by the lenient scores).

Run from the project root:  python nlu/make_colab_zip.py
"""
import sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = ["utils.py", "config.yaml", "data/traits.json", "data/form_checks.py", "data/negatives/prepare_negatives.py",
         "nlu/__init__.py", "nlu/joint_model.py", "nlu/normalize.py", "nlu/train_nlu.py",
         "data/nlu/corpus/train.jsonl", "data/nlu/corpus/val.jsonl", "data/nlu/corpus/test.jsonl"]


def main():
    missing = [f for f in FILES if not (ROOT / f).exists()]
    if missing:
        sys.exit(f"missing: {missing} (run data/nlu/prepare_nlu.py first for the corpus)")
    out = ROOT / "nlu_colab.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(ROOT / f, f)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(FILES)} files): upload it in the notebook's first cell")


if __name__ == "__main__":
    main()
