"""Phase 3 shared settings: train the 8k BPE tokenizer on the quatrain and diss training splits.

Run from the project root:  python generation/train_tokenizer.py
Only training splits are used, so validation and test text stays unseen (including the held-out traits).
"""
import contextlib, json, sys
from collections import Counter
from datetime import date
from pathlib import Path

import sentencepiece as spm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import load_config, project_path


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def training_text(quatrains, disses):
    """One sentence per poem line, plus the trait names and intensity words that appear in the prefix."""
    lines = [l for q in quatrains for l in q["lines"]] + [l for d in disses for l in d["lines"]]
    words = sorted({t for d in disses for t in d["traits"]} | {"mild", "harsh", "none"})
    return lines + words


def encode_stats(sp, lines):
    ids = [sp.encode(l) for l in lines]
    n = sum(map(len, ids))
    return {"lines": len(lines), "tokens": n, "tokens_per_line": round(n / max(len(lines), 1), 2),
            "unk": sum(i == sp.unk_id() for x in ids for i in x),
            "byte_fallback": sum(sp.is_byte(i) for x in ids for i in x),
            "roundtrip_ok": all(sp.decode(x) == l for x, l in zip(ids, lines))}


def main():
    cfg = load_config()
    tok = cfg["tokenizer"]
    prefix = project_path(cfg["paths"]["tokenizer"])
    prefix.parent.mkdir(parents=True, exist_ok=True)
    qdir, ddir = project_path(cfg["paths"]["corpus_dir"]), project_path(cfg["paths"]["diss_dir"])

    q_train, d_train = read_jsonl(qdir / "quatrains_train.jsonl"), read_jsonl(ddir / "train.jsonl")
    text = training_text(q_train, d_train)

    # train from the output folder with a bare prefix: the model file stores the prefix, and an absolute path
    # would make it differ per machine (and leak the local folder layout)
    with contextlib.chdir(prefix.parent):
        spm.SentencePieceTrainer.train(
            sentence_iterator=iter(text), model_prefix=prefix.name, model_type="bpe",
            vocab_size=tok["vocab_size"], character_coverage=1.0, byte_fallback=True,
            normalization_rule_name="identity",       # text is already normalized (utils.normalize_text)
            user_defined_symbols=tok["special"],
            pad_id=0, unk_id=1, bos_id=2, eos_id=3,
            pad_piece="<pad>", unk_piece="<unk>", bos_piece="<bos>", eos_piece="<eos>",
            num_threads=4, minloglevel=2)             # BPE merges are deterministic, so no seed is needed

    sp = spm.SentencePieceProcessor(model_file=str(prefix) + ".model")
    for s in tok["special"]:                      # written in the text, each must come out as its own id
        assert sp.piece_to_id(s) in sp.encode(f"a {s} b"), f"{s} is not a single token"

    stats = {}
    for name, path in [("quatrains_train", qdir / "quatrains_train.jsonl"), ("quatrains_val", qdir / "quatrains_val.jsonl"),
                       ("disses_train", ddir / "train.jsonl"), ("disses_val", ddir / "val.jsonl"),
                       ("disses_test", ddir / "test.jsonl")]:
        stats[name] = encode_stats(sp, [l for r in read_jsonl(path) for l in r["lines"]])
    traits = json.load(open(project_path(cfg["paths"]["traits"]), encoding="utf-8"))
    pieces = Counter(len(sp.encode(t)) for t in traits)

    meta = {"date": date.today().isoformat(), "model_type": "bpe", "vocab_size": sp.get_piece_size(),
            "special": {s: sp.piece_to_id(s) for s in ["<pad>", "<unk>", "<bos>", "<eos>", *tok["special"]]},
            "trained_on": {"quatrain_lines": sum(len(q["lines"]) for q in q_train),
                           "diss_lines": sum(len(d["lines"]) for d in d_train)},
            "encode": stats, "trait_pieces": dict(sorted(pieces.items()))}
    json.dump(meta, open(prefix.parent / "meta.json", "w", encoding="utf-8"), indent=2)

    print(f"vocab {meta['vocab_size']} | special ids {meta['special']}")
    for name, s in stats.items():
        print(f"  {name:16s} {s['tokens']:>8,} tokens  {s['tokens_per_line']:5.2f}/line  "
              f"unk {s['unk']}  bytes {s['byte_fallback']}  roundtrip {'ok' if s['roundtrip_ok'] else 'FAILED'}")
    print(f"traits split into n pieces: {meta['trait_pieces']}")
    print(f"wrote {prefix}.model")


if __name__ == "__main__":
    main()
