"""Phase 3 shared settings: turn quatrains and disses into token sequences for the from-scratch generators.

  <traits> confident bold <intensity> harsh <rhymes> proud loud wise eyes <poem> line1 <nl> line2 <nl> line3 <nl> line4 <eos>

Stage 1 quatrains have an empty <traits> field and intensity "none". Each segment is encoded on its own and the ids
are joined, because encoding the whole string puts a stray "▁" token before every special token.
The loss mask covers the poem only (everything after <poem>, including <eos>).

Check the data from the project root:  python generation/sequences.py
"""
import json, sys
from pathlib import Path

import sentencepiece as spm
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import load_config, project_path

STAGE_FILES = {                     # stage -> split -> (config path key, file name)
    1: {"train": ("corpus_dir", "quatrains_train.jsonl"), "val": ("corpus_dir", "quatrains_val.jsonl")},
    2: {"train": ("diss_dir", "train.jsonl"), "val": ("diss_dir", "val.jsonl"), "test": ("diss_dir", "test.jsonl")},
}


class PoemCodec:
    """Encodes the conditioning prefix and the poem, and decodes generated ids back to four lines."""

    def __init__(self, cfg=None):
        cfg = cfg or load_config()
        self.sp = spm.SentencePieceProcessor(model_file=str(project_path(cfg["paths"]["tokenizer"])) + ".model")
        self.id = {s: self.sp.piece_to_id(s) for s in cfg["tokenizer"]["special"]}
        self.pad, self.eos = self.sp.pad_id(), self.sp.eos_id()
        self.vocab_size = self.sp.get_piece_size()

    def words(self, words):
        return self.sp.encode(" ".join(words)) if words else []

    def prefix(self, traits, intensity, end_words):
        """Everything the model conditions on, ending with <poem>. Used for training and for generation."""
        return ([self.id["<traits>"], *self.words(traits), self.id["<intensity>"], *self.words([intensity]),
                 self.id["<rhymes>"], *self.words(end_words), self.id["<poem>"]])

    def poem(self, lines):
        ids = []
        for i, line in enumerate(lines):
            ids += self.sp.encode(line) + [self.id["<nl>"] if i < len(lines) - 1 else self.eos]
        return ids

    def example(self, lines, end_words, traits=(), intensity="none"):
        p, q = self.prefix(list(traits), intensity, end_words), self.poem(lines)
        return {"ids": p + q, "mask": [0] * len(p) + [1] * len(q)}

    def decode_lines(self, poem_ids):
        """Poem ids (after <poem>) -> list of lines; stops at <eos>."""
        lines, cur = [], []
        for i in poem_ids:
            if i == self.eos:
                break
            if i == self.id["<nl>"]:
                lines.append(cur)
                cur = []
            else:
                cur.append(i)
        if cur or not lines:                  # a trailing <nl> (generation stopped at a 4th one) adds no line
            lines.append(cur)
        return [self.sp.decode(l) for l in lines]


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def load_split(codec, stage, split, cfg=None):
    """Stage 1: quatrains (no traits, intensity none). Stage 2: disses with their traits and intensity."""
    cfg = cfg or load_config()
    key, name = STAGE_FILES[stage][split]
    rows = read_jsonl(project_path(cfg["paths"][key]) / name)
    if stage == 1:
        return [codec.example(r["lines"], [w for p in r["rhymes"] for w in p]) for r in rows]
    return [codec.example(r["lines"], r["end_words"], r["traits"], r["intensity"]) for r in rows]


class SequenceDataset(torch.utils.data.Dataset):
    def __init__(self, examples):
        self.examples = examples

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, i):
        return self.examples[i]


def make_collate(pad_id):
    """Pads a batch; next-token targets are the ids shifted left, and the loss mask is shifted with them."""
    def collate(batch):
        n = max(len(b["ids"]) for b in batch) - 1
        x = torch.full((len(batch), n), pad_id, dtype=torch.long)
        y = torch.full((len(batch), n), pad_id, dtype=torch.long)
        m = torch.zeros((len(batch), n), dtype=torch.float)
        lengths = torch.tensor([len(b["ids"]) - 1 for b in batch])
        for k, b in enumerate(batch):
            ids, mask = torch.tensor(b["ids"]), torch.tensor(b["mask"], dtype=torch.float)
            x[k, :len(ids) - 1], y[k, :len(ids) - 1], m[k, :len(ids) - 1] = ids[:-1], ids[1:], mask[1:]
        return {"input": x, "target": y, "mask": m, "lengths": lengths}
    return collate


def main():
    """Builds every split and checks that the sequences decode back to the original poems."""
    cfg = load_config()
    codec = PoemCodec(cfg)
    stray = codec.sp.piece_to_id("▁")
    for stage, splits in STAGE_FILES.items():
        for split in splits:
            key, name = STAGE_FILES[stage][split]
            rows = read_jsonl(project_path(cfg["paths"][key]) / name)
            ex = load_split(codec, stage, split, cfg)
            ok = sum(codec.decode_lines(e["ids"][e["mask"].index(1):]) == r["lines"] for e, r in zip(ex, rows))
            lens = sorted(len(e["ids"]) for e in ex)
            print(f"stage {stage} {split:5s} {len(ex):>6} examples | decode ok {ok}/{len(ex)} | "
                  f"length median {lens[len(lens) // 2]} max {lens[-1]} | "
                  f"poem tokens {sum(sum(e['mask']) for e in ex):,} | stray '▁' {sum(e['ids'].count(stray) for e in ex)}")

    e = load_split(codec, 2, "train", cfg)[0]
    print("\nexample:", " ".join(codec.sp.id_to_piece(i) for i in e["ids"]))
    batch = make_collate(codec.pad)(load_split(codec, 1, "val", cfg)[:4])
    print("batch shapes:", {k: tuple(v.shape) for k, v in batch.items()})


if __name__ == "__main__":
    main()
