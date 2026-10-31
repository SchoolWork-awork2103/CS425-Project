"""Phase 1e: build the reranker negatives for every training trait.

  flat, non_rhyming  the LLM's deliberately bad quatrains (negatives_gen.ipynb)
  off_topic          fine quatrains from the quatrain corpus, which are not roasts
  wrong_trait        real training disses, labelled with a trait they were not written for
  review_dropped     the disses dropped in manual review

Apart from its own flaw, every negative passes the disses' form check (cfg["diss_form"]), so rhyme and line length
can't tell it apart from a real diss. non_rhyming must not rhyme and only has to pass the length checks.
off_topic and wrong_trait come from the train splits only, so no val or test text ends up in the negatives.

Run from the project root, after `data/disses/prepare_disses.py auto` (or `finalize`):
  python data/negatives/prepare_negatives.py
"""
import itertools, json, random, sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # data/: form_checks
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root: utils
from utils import load_config, normalize_text, project_path
from form_checks import check, drop_reason, last_word, rhymes

LENGTH_REASONS = {"syllable_range", "pair_unbalanced", "oov"}   # the form checks a non-rhyming quatrain must pass
PER_TRAIT = 20      # off_topic and wrong_trait negatives per training trait
# traits close enough that a diss for one still fits the other; wrong_trait never swaps within a group
CLOSE = [
    {"smart", "knowledgeable", "bookish", "wise", "curious", "eloquent"},
    {"hardworking", "ambitious", "disciplined", "entrepreneurial", "competitive"},
    {"organized", "tidy", "meticulous", "responsible", "punctual"},
    {"calm", "easygoing", "patient"},
    {"generous", "caring", "helpful", "loyal"},
    {"outgoing", "funny", "charming"},
    {"adventurous", "spontaneous", "worldly"},
    {"athletic", "healthy"},
    {"creative", "musical"},
]


def close_to(trait):
    return {trait}.union(*(g for g in CLOSE if trait in g))


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def main():
    cfg = load_config()
    rng = random.Random(cfg["seed"])
    traits = json.load(open(project_path(cfg["paths"]["traits"]), encoding="utf-8"))
    train_traits = [t for t, v in traits.items() if not v["heldout"]]
    src = project_path(cfg["paths"]["negatives_raw"])
    diss_dir = project_path(cfg["paths"]["diss_dir"])
    out = project_path(cfg["paths"]["negatives_dir"])
    out.mkdir(parents=True, exist_ok=True)

    # flat and non_rhyming from the LLM
    raw = read_jsonl(src)
    seen, rows, dropped = set(), [], Counter()
    for r in raw:
        why = drop_reason(r["lines"])
        lines = [normalize_text(l) for l in r["lines"]]
        if not why and len(lines) != 4:
            why = "line_count"
        if not why:
            reasons = check(lines, **cfg["diss_form"])["reasons"]
            if r["type"] == "non_rhyming":
                ends = [last_word(l) for l in lines]
                if rhymes(ends[0], ends[1]) or rhymes(ends[2], ends[3]):
                    reasons = ["rhymes_anyway"]
                else:
                    reasons = [x for x in reasons if x in LENGTH_REASONS]
            why = reasons[0] if reasons else None
        if not why and " / ".join(lines) in seen:
            why = "duplicate"
        if why:
            dropped[f"{r['type']}: {why}"] += 1
            continue
        seen.add(" / ".join(lines))
        rows.append({"type": r["type"], "traits": r["traits"], "about": None, "lines": lines})
    n_llm = len(rows)

    # off_topic: each corpus quatrain used once, from the longer half so line length is closer to the disses'
    quatrains = read_jsonl(project_path(cfg["paths"]["corpus_dir"]) / "quatrains_train.jsonl")
    quatrains.sort(key=lambda q: sum(q["syllables"]), reverse=True)
    pool = quatrains[:len(quatrains) // 2]
    rng.shuffle(pool)
    pool = iter(q for q in pool if check(q["lines"], **cfg["diss_form"])["pass"])
    for t in train_traits:
        for q in itertools.islice(pool, PER_TRAIT):
            rows.append({"type": "off_topic", "traits": [t], "about": None, "lines": q["lines"]})

    # wrong_trait: disses for other traits, never one close to the label
    disses = [d for d in read_jsonl(diss_dir / "train.jsonl") if d["traits"]]
    for t in train_traits:
        near = close_to(t)
        candidates = [d for d in disses if not near & set(d["traits"])]
        for d in rng.sample(candidates, min(PER_TRAIT, len(candidates))):
            rows.append({"type": "wrong_trait", "traits": [t], "about": d["traits"], "lines": d["lines"]})
    n_built = len(rows) - n_llm

    reviewed_drops = diss_dir / "dropped.jsonl"
    if reviewed_drops.exists():
        for r in read_jsonl(reviewed_drops):
            rows.append({"type": "review_dropped", "traits": r["traits"], "about": None, "lines": r["lines"],
                         "reason": r.get("drop_reason", "")})
    else:
        print(f"note: {reviewed_drops} not found; run `data/disses/prepare_disses.py auto` or `finalize` first to include review drops")

    with open(out / "negatives.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    meta = {"date": date.today().isoformat(), "raw": len(raw), "dropped": dict(dropped), "from_llm": n_llm,
            "from_corpora": n_built, "from_review": len(rows) - n_llm - n_built, "per_trait": PER_TRAIT,
            "close_groups": [sorted(g) for g in CLOSE], "by_type": dict(Counter(r["type"] for r in rows))}
    json.dump(meta, open(out / "meta.json", "w", encoding="utf-8"), indent=2)
    print(f"raw {len(raw)} -> {n_llm} LLM negatives | dropped {dict(dropped)}")
    print(f"+{n_built} from the quatrain and diss corpora | +{meta['from_review']} from review | by type {meta['by_type']}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
