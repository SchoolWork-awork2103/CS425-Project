"""Phase 2 / 6: compact GloVe vectors for the rhyme planner and the NLU slot normalization.

Reads glove.6B.300d.txt straight from the official glove.6B.zip (https://nlp.stanford.edu/projects/glove/, also at
https://huggingface.co/stanfordnlp/glove) and keeps the most frequent words (GloVe lists words by frequency):
  <prefix>.npy        float16 matrix, one row per word
  <prefix>.vocab.txt  the words, one per line, in row order

Run from the project root:  python data/prepare_glove.py path/to/glove.6B.zip
"""
import io, json, sys, zipfile
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import load_config, project_path

MEMBER, DIM, KEEP = "glove.6B.300d.txt", 300, 100_000


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    prefix = project_path(load_config()["paths"]["glove"])
    prefix.parent.mkdir(parents=True, exist_ok=True)

    words, rows = [], np.empty((KEEP, DIM), dtype=np.float16)
    with zipfile.ZipFile(sys.argv[1]) as z, io.TextIOWrapper(z.open(MEMBER), encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip().split(" ")
            if len(parts) != DIM + 1:
                continue
            rows[len(words)] = np.asarray(parts[1:], dtype=np.float32)
            words.append(parts[0])
            if len(words) == KEEP:
                break

    np.save(f"{prefix}.npy", rows[:len(words)])
    Path(f"{prefix}.vocab.txt").write_text("\n".join(words) + "\n", encoding="utf-8")
    meta = {"date": date.today().isoformat(), "source": "glove.6B.zip / " + MEMBER, "dim": DIM, "words": len(words),
            "dtype": "float16"}
    json.dump(meta, open(f"{prefix}.meta.json", "w"), indent=2)
    print(f"kept {len(words):,} words x {DIM} -> {prefix}.npy")


if __name__ == "__main__":
    main()
