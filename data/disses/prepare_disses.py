"""Phase 1b steps 3-6 and 1c: filter the LLM disses, build the review sheets, then split the reviewed disses.

Run from the project root, in two steps:
  python data/disses/prepare_disses.py filter     # auto filters -> data/disses/corpus/review/review_<n>.csv
  (each reviewer fills in their sheet)
  python data/disses/prepare_disses.py finalize   # reviewed sheets -> data/disses/corpus/{train,val,test}.jsonl

or, with no manual review (every diss that passes the auto filters is kept):
  python data/disses/prepare_disses.py auto       # auto filters -> data/disses/corpus/{train,val,test}.jsonl
"""
import argparse, csv, json, random, re, sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # data/: form_checks
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root: utils
from utils import load_config, normalize_text, project_path, set_seed
from form_checks import check, drop_reason, last_word, near_dup, words_of

REVIEW_COLS = ["id", "traits", "intensity", "persona", "line1", "line2", "line3", "line4",
               "decision", "reason", "note"]
REVIEW_GUIDE = """How to review the disses

Fill in two columns for every row:
  decision  keep / fix / drop
  reason    for fix or drop: humour, relevance or offensive (more than one is fine)

keep  a real burn, on the listed traits, no vulgar language, nothing hateful
fix   close, but one line is weak: edit the line1-line4 cells directly. Lines 1-2 and 3-4 must still rhyme.
drop  soft or not funny, off-trait, nonsense, vulgar, or hateful about race, religion, gender,
      sexuality or disability (appearance jokes are fine)

Traits marked "(fallback)" are generic disses that should fit anyone.
Save as CSV (UTF-8) with the same file name, then run: python data/disses/prepare_disses.py finalize
"""


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def read_csv(path):
    for enc in ("utf-8-sig", "cp1252"):        # Excel may save in either
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"cannot read {path}")


def load_blocklist(path):
    words = [l.strip().lower() for l in open(path, encoding="utf-8") if l.strip() and not l.startswith("#")]
    return re.compile(r"\b(" + "|".join(map(re.escape, words)) + r")\b")


def dedup(rows, threshold):
    """Drop exact and near-duplicates (ROUGE-L), comparing disses that share a trait set or a rhyme pair."""
    keys, groups, kept, dropped = set(), defaultdict(list), [], Counter()
    for r in rows:
        key = " / ".join(r["lines"])
        toks = [w for l in r["lines"] for w in words_of(l)]
        cnt = Counter(toks)
        buckets = [("traits", tuple(r["traits"]))] + [("pair", tuple(sorted(p))) for p in r["rhymes"]]
        if key in keys:
            dropped["duplicate"] += 1
        elif any(near_dup(toks, cnt, t, c, threshold) for b in buckets for t, c in groups[b]):
            dropped["near_duplicate"] += 1
        else:
            keys.add(key)
            for b in buckets:
                groups[b].append((toks, cnt))
            kept.append(r)
    return kept, dropped


def toxicity_scores(poems):
    from detoxify import Detoxify               # loads a ~400 MB model on first use
    model, scores = Detoxify("original"), []
    for i in range(0, len(poems), 64):
        chunk = poems[i:i + 64]
        batch = model.predict(chunk)                # a batch of one gives floats instead of lists
        scores += [{k: round(float(v[j] if isinstance(v, list) else v), 4) for k, v in batch.items()}
                   for j in range(len(chunk))]
    return scores


def cmd_filter(cfg, args, sheets=True):
    seed = set_seed(cfg["seed"])
    src = project_path(cfg["paths"]["disses_raw"])
    out = project_path(cfg["paths"]["diss_dir"])
    review_dir = out / "review"
    if sheets and review_dir.exists() and any(review_dir.glob("review_*.csv")) and not args.force:
        sys.exit(f"{review_dir} already has review sheets. Rerunning would overwrite the manual review; "
                 "pass --force if that is really what you want.")
    out.mkdir(parents=True, exist_ok=True)

    raw, dropped, rows = read_jsonl(src), Counter(), []
    for r in raw:
        why = drop_reason(r["lines"])
        lines = [normalize_text(l) for l in r["lines"]]
        if not why and [last_word(l) for l in lines] != [w.lower() for p in r["rhymes"] for w in p]:
            why = "end_word_mismatch"
        if why:
            dropped[why] += 1
            continue
        rows.append({**r, "lines": lines, "rhymes": [[w.lower() for w in p] for p in r["rhymes"]]})

    rows, dup = dedup(rows, cfg["data"]["rouge_dedup"])
    dropped.update(dup)

    block = load_blocklist(project_path(cfg["paths"]["blocklist"]))
    limits = cfg["toxicity"]
    scores = toxicity_scores(["\n".join(r["lines"]) for r in rows])
    unknown = set(limits) - set(scores[0]) if scores else set()
    if unknown:
        sys.exit(f"config toxicity limits {sorted(unknown)} are not Detoxify scores; use {sorted(scores[0])}")
    clean = []
    for r, s in zip(rows, scores):
        r["toxicity"] = s
        hit = block.search(" ".join(r["lines"]))
        over = [k for k, lim in limits.items() if s.get(k, 0) >= lim]
        if hit:
            dropped["blocklist"] += 1
        elif over:
            dropped["toxicity:" + over[0]] += 1
        else:
            clean.append(r)
    write_jsonl(out / "filtered.jsonl", clean)

    # review sheets: shuffled, split evenly across reviewers
    n = (getattr(args, "reviewers", None) or cfg["data"]["reviewers"]) if sheets else 0
    if sheets:
        review_dir.mkdir(exist_ok=True)
        order = clean[:]
        random.Random(seed).shuffle(order)
        for k in range(n):
            with open(review_dir / f"review_{k + 1}.csv", "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(REVIEW_COLS)
                for r in order[k::n]:
                    w.writerow([r["id"], ", ".join(r["traits"]) or "(fallback)", r["intensity"], r["persona"],
                                *r["lines"], "", "", ""])
        (review_dir / "HOW_TO_REVIEW.txt").write_text(REVIEW_GUIDE, encoding="utf-8")

    meta = {"date": date.today().isoformat(), "raw": len(raw), "dropped": dict(dropped),
            "after_filters": len(clean), "reviewers": n, "toxicity_limits": limits,
            "by_kind": dict(Counter(r["kind"] for r in clean)),
            "by_intensity": dict(Counter(r["intensity"] for r in clean))}
    json.dump(meta, open(out / "filter_meta.json", "w", encoding="utf-8"), indent=2)
    print(f"raw {len(raw)} -> {len(clean)} after filters | dropped {dict(dropped)}")
    print(f"by kind {meta['by_kind']} | by intensity {meta['by_intensity']}")
    for k in limits:
        vals = sorted(s[k] for s in scores)
        if vals:
            print(f"  {k:16s} median {vals[len(vals) // 2]:.3f}  p95 {vals[int(len(vals) * .95)]:.3f}  "
                  f"limit {limits[k]}")
    if sheets:
        print(f"wrote {n} review sheets to {review_dir}")


def cmd_finalize(cfg, args, review=True):
    seed = set_seed(cfg["seed"])
    out = project_path(cfg["paths"]["diss_dir"])
    sheets = sorted((out / "review").glob("review_*.csv"))
    if not (out / "filtered.jsonl").exists() or (review and not sheets):
        sys.exit("No filtered disses or review sheets found; run the filter step first.")
    by_id = {r["id"]: r for r in read_jsonl(out / "filtered.jsonl")}

    reviewed, missing = {}, Counter()
    if not review:
        reviewed = {i: ("keep", {}) for i in by_id}
    for path in sheets if review else []:
        for row in read_csv(path):
            d = (row.get("decision") or "").strip().lower()
            if d not in ("keep", "fix", "drop"):
                missing[path.name] += 1
                continue
            reviewed[int(row["id"])] = (d, row)
    if missing:
        sys.exit(f"Rows without keep / fix / drop: {dict(missing)}. Finish the review first.")

    kept, dropped, decisions = [], [], Counter()
    for i, (d, row) in reviewed.items():
        r = by_id[i]
        reason = (row.get("reason") or "").strip().lower()
        if d == "fix":
            lines = [normalize_text(row[f"line{k}"]) for k in range(1, 5)]
            c = check(lines, **cfg["diss_form"])
            if not c["pass"]:
                d, reason = "drop", "fix_failed_form: " + ", ".join(c["reasons"])
            else:
                r = {**r, "lines": lines, "rhymes": [c["ends"][0:2], c["ends"][2:4]], "syllables": c["syllables"]}
        decisions[d] += 1
        if d == "drop":
            dropped.append({**r, "drop_reason": reason})
            continue
        ends = [last_word(l) for l in r["lines"]]
        kept.append({"id": r["id"], "traits": r["traits"], "intensity": r["intensity"], "kind": r["kind"],
                     "persona": r["persona"], "end_words": ends, "rhymes": [ends[0:2], ends[2:4]],
                     "poem": "\n".join(r["lines"]), "lines": r["lines"], "syllables": r["syllables"],
                     "review": d if review else "auto"})

    # 80/10/10 over training traits and the fallback disses; held-out traits go to test only
    rng = random.Random(seed)
    pool = [r for r in kept if r["kind"] != "heldout"]
    rng.shuffle(pool)
    f_train, f_val, _ = cfg["data"]["diss_split"]
    a, b = int(f_train * len(pool)), int((f_train + f_val) * len(pool))
    splits = {"train": pool[:a], "val": pool[a:b], "test": pool[b:] + [r for r in kept if r["kind"] == "heldout"]}
    for name, rows in splits.items():
        write_jsonl(out / f"{name}.jsonl", rows)
    write_jsonl(out / "dropped.jsonl", dropped)          # reranker negatives (1e)

    meta = {"date": date.today().isoformat(), "manual_review": review,
            "reviewed": len(reviewed) if review else 0, "decisions": dict(decisions),
            "kept": len(kept), "splits": {k: len(v) for k, v in splits.items()},
            "test_heldout": sum(r["kind"] == "heldout" for r in splits["test"]),
            "by_kind": dict(Counter(r["kind"] for r in kept)),
            "by_intensity": dict(Counter(r["intensity"] for r in kept)),
            "drop_reasons": dict(Counter(r["drop_reason"] or "(none given)" for r in dropped))}
    json.dump(meta, open(out / "meta.json", "w", encoding="utf-8"), indent=2)
    print(f"{'reviewed' if review else 'no manual review, kept all'} {len(reviewed)} | {dict(decisions)} | "
          f"kept {len(kept)}")
    print(f"splits {meta['splits']} (test includes {meta['test_heldout']} held-out-trait disses)")
    print(f"wrote {out}")


def cmd_auto(cfg, args):
    """Filter and split with no manual review: the generation judge (score >= 4) stands in for it."""
    cmd_filter(cfg, args, sheets=False)
    cmd_finalize(cfg, args, review=False)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("filter")
    f.add_argument("--reviewers", type=int, help="number of review sheets (default: config data.reviewers)")
    f.add_argument("--force", action="store_true", help="overwrite existing review sheets")
    sub.add_parser("finalize")
    sub.add_parser("auto")
    args = p.parse_args()
    cfg = load_config()
    {"filter": cmd_filter, "finalize": cmd_finalize, "auto": cmd_auto}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
