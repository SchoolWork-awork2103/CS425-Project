"""Phase 1d: turn the LLM's NLU messages into intent + BIO slot data, split it, and export a spot-check sheet.

Run from the project root:  python data/nlu/prepare_nlu.py
"""
import csv, json, random, re, sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root: utils
from utils import load_config, project_path, set_seed

TOKEN_RE = re.compile(r"\S+")


def bio_tags(text, spans):
    """Whitespace tokens and their BIO tags, or None if a span is missing from the text or spans overlap."""
    taken, found = set(), []
    for s in spans:
        i = text.lower().find(s["span"].lower())
        if i < 0 or not s["span"].strip():
            return None
        chars = set(range(i, i + len(s["span"])))
        if chars & taken:
            return None
        taken |= chars
        found.append((i, i + len(s["span"]), s["trait"]))
    tokens, tags = [], []
    for m in TOKEN_RE.finditer(text):
        tokens.append(m.group(0))
        hit = [f for f in found if m.start() < f[1] and m.end() > f[0]]
        if not hit:
            tags.append("O")
        else:
            tags.append("I-TRAIT" if tags and tags[-1] != "O" and m.start() > hit[0][0] else "B-TRAIT")
    order = [t for _, _, t in sorted(found)]
    return tokens, tags, order


def main():
    cfg = load_config()
    seed = set_seed(cfg["seed"])
    traits = json.load(open(project_path(cfg["paths"]["traits"]), encoding="utf-8"))
    src = project_path(cfg["paths"]["nlu_raw"])
    out = project_path(cfg["paths"]["nlu_dir"])
    out.mkdir(parents=True, exist_ok=True)

    raw = [json.loads(l) for l in open(src, encoding="utf-8")]
    for r in raw:
        r["text"] = re.sub(r"\s+", " ", r["text"]).strip()
    intents_of = defaultdict(set)                  # the same message under two intents can't be labelled
    for r in raw:
        intents_of[r["text"].lower()].add(r["intent"])
    seen, rows, dropped = set(), [], Counter()
    for r in raw:
        text = r["text"]
        if not text:
            dropped["empty"] += 1
            continue
        if len(intents_of[text.lower()]) > 1:
            dropped["ambiguous_intent"] += 1
            continue
        if text.lower() in seen:
            dropped["duplicate"] += 1
            continue
        spans = [s for s in r["spans"] if isinstance(s.get("span"), str) and s.get("trait") in r["traits"]]
        if r["traits"] and not spans:
            dropped["no_span"] += 1
            continue
        tagged = bio_tags(text, spans)
        if tagged is None:
            dropped["span_not_in_text"] += 1
            continue
        tokens, tags, found = tagged
        seen.add(text.lower())
        rows.append({"text": text, "tokens": tokens, "tags": tags, "intent": r["intent"],
                     "traits": found, "group": r["group"]})

    # 80/10/10 within each intent; messages about held-out traits go to test only
    rng = random.Random(seed)
    f_train, f_val, _ = cfg["data"]["nlu_split"]
    splits = defaultdict(list)
    by_intent = defaultdict(list)
    for r in rows:
        if r["group"] == "heldout":
            splits["test"].append(r)
        else:
            by_intent[r["intent"]].append(r)
    for intent in sorted(by_intent):
        items = by_intent[intent]
        rng.shuffle(items)
        a, b = int(f_train * len(items)), int((f_train + f_val) * len(items))
        splits["train"] += items[:a]; splits["val"] += items[a:b]; splits["test"] += items[b:]
    for name in ("train", "val", "test"):
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps({k: v for k, v in r.items() if k != "group"}, ensure_ascii=False) + "\n"
                         for r in splits[name])

    # spot-check sheet: mark ok = y / n for about 10% of the messages
    sample = rng.sample(rows, max(1, round(cfg["data"]["nlu_spot_check_frac"] * len(rows))))
    with open(out / "spot_check.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["intent", "traits", "tagged_text", "ok", "note"])
        for r in sample:
            marked = " ".join(f"[{t}]" if g != "O" else t for t, g in zip(r["tokens"], r["tags"]))
            w.writerow([r["intent"], ", ".join(r["traits"]), marked, "", ""])

    unknown = {t for r in rows for t in r["traits"] if t not in traits}
    meta = {"date": date.today().isoformat(), "raw": len(raw), "dropped": dict(dropped), "kept": len(rows),
            "splits": {k: len(v) for k, v in splits.items()},
            "by_intent": dict(Counter(r["intent"] for r in rows)),
            "heldout_in_test": sum(r["group"] == "heldout" for r in rows), "spot_check": len(sample)}
    json.dump(meta, open(out / "meta.json", "w", encoding="utf-8"), indent=2)
    print(f"raw {len(raw)} -> kept {len(rows)} | dropped {dict(dropped)}")
    print(f"by intent {meta['by_intent']}")
    print(f"splits {meta['splits']} (test includes {meta['heldout_in_test']} held-out-trait messages)")
    if unknown:
        print("warning: traits not in traits.json:", sorted(unknown))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
