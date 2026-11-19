"""Phase 5 step 5: the hand-rated candidates for tuning the reranker weights.

Run from the project root, in order:
  python reranker/rating_pool.py prompts                # val-split prompts + rhyme plans -> prompts.jsonl (needs GloVe)
  python reranker/rating_pool.py generate --system A    # -> candidates_A.jsonl (CPU is fine)
  python reranker/rating_pool.py generate --system D --ckpt-dir /content/drive/MyDrive/CS425/checkpoints   # on Colab
  python reranker/rating_pool.py sheets                 # hard filters, 5 per prompt -> blind sheets/rater_<k>.csv
  (each rater fills in the rating column of their own sheet)
  python reranker/rating_pool.py collect                # checks the sheets, rater agreement -> ratings.jsonl

The prompts are the traits and intensity of validation disses, never the 50 frozen eval prompts, so tuning does not
see the evaluation. End words come from the rhyme planner, and each prompt gets candidates the way it would at run
time (top plans x samples per plan), all from one generator: the reranker only ever compares candidates for the same
request, and log-probabilities of A and D are on different scales. Settings are reranker.tuning in config.yaml; files
go to paths.rerank_ratings, the agreement numbers to eval/results/rerank_tuning/.
"""
import argparse, csv, json, random, sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "generation"), str(ROOT / "data" / "disses")]
from utils import load_config, project_path

SHEET_COLS = ["item", "traits", "intensity", "line1", "line2", "line3", "line4", "rating", "note"]
RATING_GUIDE = """How to rate the roasts

Each row is a four-line roast written for someone who asked to be roasted for the listed traits, at the listed
intensity. Rows for the same request are next to each other. Fill in one column for every row:

  rating  1-5, how good the poem is as a reply to that request

5  you would happily send it: clearly about the traits, a real joke, both couplets rhyme (lines 1-2, lines 3-4),
   reads smoothly
4  good, with one small weakness: a forced rhyme, a flat line, a bit generic
3  fine but forgettable: on topic and readable, but not funny, or one line is clumsy
2  weak: barely about the traits, a couplet doesn't rhyme, or hard to follow
1  unusable: nonsense, broken lines, or offensive about race, religion, gender, sexuality or disability

- Intensity: "harsh" should bite and "mild" should be gentle teasing. A clear mismatch costs a point.
- "(none)" under traits means the request named no trait: any fair generic roast is on topic.
- Rate each poem on its own merits. Ties are fine, and so is using 1 and 5.
- The note column is optional (e.g. why you gave a 1). Don't change any other column or the order of the rows.
- Rate alone: don't compare ratings with the other rater until both sheets are done.

Save as CSV (UTF-8) with the same file name, then run: python reranker/rating_pool.py collect
"""


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def cmd_prompts(cfg, args):
    from phonetics.planner import RhymePlanner
    t, out = cfg["reranker"]["tuning"], project_path(cfg["paths"]["rerank_ratings"])
    if (out / "prompts.jsonl").exists() and not args.force:
        sys.exit(f"{out / 'prompts.jsonl'} exists; the candidates and sheets are built on it. Pass --force to redo it.")
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg["seed"])
    rows = read_jsonl(project_path(cfg["paths"]["diss_dir"]) / "val.jsonl")
    rng.shuffle(rows)
    systems = [s for s, n in t["prompts"].items() for _ in range(n)]
    rng.shuffle(systems)
    quota = {"mild": len(systems) - len(systems) // 2, "harsh": len(systems) // 2}

    planner, prompts, seen = RhymePlanner(cfg), [], set()
    for r in rows:                              # half mild, half harsh, no trait set twice
        key = tuple(sorted(r["traits"]))
        if len(prompts) == len(systems) or quota[r["intensity"]] == 0 or key in seen:
            continue
        plans = planner.plan(r["traits"], k=t["plans"])
        if len(plans) < t["plans"]:
            continue
        seen.add(key)
        quota[r["intensity"]] -= 1
        prompts.append({"id": len(prompts) + 1, "system": systems[len(prompts)], "traits": r["traits"],
                        "intensity": r["intensity"], "kind": r["kind"], "diss_id": r["id"],
                        "plans": [p["end_words"] for p in plans]})
    write_jsonl(out / "prompts.jsonl", prompts)
    print(f"{len(prompts)} prompts | {dict(Counter(p['system'] for p in prompts))} | "
          f"{dict(Counter(p['kind'] for p in prompts))} | {dict(Counter(p['intensity'] for p in prompts))}")
    print(f"wrote {out / 'prompts.jsonl'}")


def cmd_generate(cfg, args):
    import torch
    t, src = cfg["reranker"]["tuning"], project_path(cfg["paths"]["rerank_ratings"])
    out = Path(args.out_dir) if args.out_dir else src
    out.mkdir(parents=True, exist_ok=True)
    prompts = [p for p in read_jsonl(src / "prompts.jsonl") if p["system"] == args.system]
    ckpt = Path(args.ckpt_dir or project_path(cfg["paths"]["checkpoints"])) / t["checkpoints"][args.system]
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if args.system == "A":
        from gru_lm import generate, load_generator
        model, codec = load_generator(ckpt, cfg, device)
    else:
        from qwen_lora import generate, load_generator
        model, codec = load_generator(ckpt, device)          # codec: the Qwen tokenizer

    rows = []
    for p in prompts:
        for j, end_words in enumerate(p["plans"]):
            torch.manual_seed(cfg["seed"] + 100 * p["id"] + j)
            samples = generate(model, codec, p["traits"], p["intensity"], end_words, n=t["per_plan"], device=device)
            rows += [{"prompt": p["id"], "system": args.system, "plan": j, "sample": k, "end_words": end_words,
                      "lines": s["lines"], "norm_logprob": round(s["norm_logprob"], 4)} for k, s in enumerate(samples)]
        print(f"prompt {p['id']} done ({', '.join(p['traits']) or 'no traits'} | {p['intensity']})")
    write_jsonl(out / f"candidates_{args.system}.jsonl", rows)
    print(f"{len(rows)} candidates from {len(prompts)} prompts on {device}; wrote {out / f'candidates_{args.system}.jsonl'}")


def cmd_sheets(cfg, args):
    from phonetics import lexical_score
    from prepare_disses import toxicity_scores
    t, d = cfg["reranker"]["tuning"], project_path(cfg["paths"]["rerank_ratings"])
    sheet_dir = d / "sheets"
    if any(sheet_dir.glob("rater_*.csv")) and not args.force:
        sys.exit(f"{sheet_dir} already has rating sheets. Rerunning would overwrite the ratings; pass --force if that "
                 "is really what you want.")
    prompts = {p["id"]: p for p in read_jsonl(d / "prompts.jsonl")}
    cands = []
    for s in t["prompts"]:
        path = d / f"candidates_{s}.jsonl"
        if not path.exists():
            sys.exit(f"{path} missing: run `python reranker/rating_pool.py generate --system {s}` first")
        rows = read_jsonl(path)
        stale = [c for c in rows if c["prompt"] not in prompts or prompts[c["prompt"]]["system"] != s
                 or prompts[c["prompt"]]["plans"][c["plan"]] != c["end_words"]]
        if stale:
            sys.exit(f"{path.name} was made from an older prompts.jsonl ({len(stale)} of {len(rows)} candidates don't "
                     f"match it): run `python reranker/rating_pool.py generate --system {s}` again")
        cands += rows

    # the reranker's hard filters, so no rating is spent on a candidate it would never rank
    vocab = set(Path(f"{project_path(cfg['paths']['glove'])}.vocab.txt").read_text(encoding="utf-8").split("\n"))
    limits, lex_min = cfg["toxicity"], cfg["reranker"]["lexical_min"]
    scores = toxicity_scores(["\n".join(c["lines"]) for c in cands])
    pools, seen, dropped = defaultdict(list), set(), Counter()
    for c, s in zip(cands, scores):
        over = [k for k, lim in limits.items() if s.get(k, 0) >= lim]
        key = (c["prompt"], " / ".join(c["lines"]))
        if len(c["lines"]) != 4 or not all(c["lines"]):
            dropped["not_4_lines"] += 1
        elif lexical_score(c["lines"], vocab) < lex_min:
            dropped["lexical"] += 1
        elif over:
            dropped["toxicity:" + over[0]] += 1
        elif key in seen:
            dropped["duplicate"] += 1
        else:
            seen.add(key)
            pools[c["prompt"]].append({**c, "toxicity": s})

    rng = random.Random(cfg["seed"])
    items, short = [], {}
    for pid in prompts:
        if len(pools[pid]) < t["shown"]:
            short[pid] = len(pools[pid])
        items += rng.sample(pools[pid], min(t["shown"], len(pools[pid])))
    numbers = list(range(1, len(items) + 1))
    rng.shuffle(numbers)                        # item numbers say nothing about the system, plan or prompt
    for n, c in zip(numbers, items):
        c["item"] = n
    items.sort(key=lambda c: c["item"])
    write_jsonl(d / "items.jsonl", items)

    sheet_dir.mkdir(exist_ok=True)
    for k in range(t["raters"]):                # each rater gets their own order of requests and of poems within one
        r = random.Random(cfg["seed"] + k + 1)
        order = list(prompts)
        r.shuffle(order)
        with open(sheet_dir / f"rater_{k + 1}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(SHEET_COLS)
            for pid in order:
                group = [c for c in items if c["prompt"] == pid]
                r.shuffle(group)
                for c in group:
                    w.writerow([c["item"], ", ".join(prompts[pid]["traits"]) or "(none)", prompts[pid]["intensity"],
                                *c["lines"], "", ""])
    (sheet_dir / "HOW_TO_RATE.txt").write_text(RATING_GUIDE, encoding="utf-8")

    meta = {"date": date.today().isoformat(), "candidates": len(cands), "dropped": dict(dropped),
            "after_filters": sum(len(v) for v in pools.values()), "items": len(items), "raters": t["raters"],
            "lexical_min": lex_min, "toxicity_limits": limits, "short_prompts": short,
            "items_by_system": dict(Counter(c["system"] for c in items))}
    json.dump(meta, open(d / "sheets_meta.json", "w", encoding="utf-8"), indent=2)
    print(f"{len(cands)} candidates -> {meta['after_filters']} after filters | dropped {dict(dropped)}")
    print(f"{len(items)} items {meta['items_by_system']} on {t['raters']} sheets in {sheet_dir}")
    if short:
        print(f"note: fewer than {t['shown']} candidates left for prompts {short}")


def agreement(a, b, groups):
    """Rank correlation of two raters over all items and within each prompt, and how often they agree exactly or
    within one point. a, b: {item: rating}; groups: lists of items for the same prompt."""
    from scipy.stats import spearmanr
    items = sorted(a)
    within = [spearmanr([a[i] for i in g], [b[i] for i in g])[0] for g in groups]
    within = [x for x in within if x == x]      # a prompt where either rater gave one score throughout has none
    return {"spearman": round(float(spearmanr([a[i] for i in items], [b[i] for i in items])[0]), 4),
            "spearman_within_prompt": round(sum(within) / len(within), 4) if within else None,
            "prompts_with_within": len(within),
            "exact": round(sum(a[i] == b[i] for i in items) / len(items), 4),
            "within_1": round(sum(abs(a[i] - b[i]) <= 1 for i in items) / len(items), 4)}


def cmd_collect(cfg, args):
    from prepare_disses import read_csv
    d = project_path(cfg["paths"]["rerank_ratings"])
    items = {c["item"]: c for c in read_jsonl(d / "items.jsonl")}
    sheets = sorted((d / "sheets").glob("rater_*.csv"))
    if len(sheets) < 2:
        sys.exit(f"found {len(sheets)} rating sheets in {d / 'sheets'}; the tuning needs at least two raters")

    ratings, problems = {}, []
    for path in sheets:
        got = {}
        for row in read_csv(path):
            v = (row.get("rating") or "").strip()
            try:
                x = float(v)                    # Excel may save 4 as "4.0"
            except ValueError:
                x = None
            if x not in (1, 2, 3, 4, 5):
                problems.append(f"{path.name} item {row.get('item')}: {v!r}")
                continue
            got[int(row["item"])] = int(x)
        if set(got) != set(items) and not problems:
            problems.append(f"{path.name}: items {sorted(set(items) - set(got))[:10]} missing")
        ratings[path.stem] = got
    if problems:
        sys.exit(f"{len(problems)} ratings missing or not 1-5, e.g. {problems[:10]}. Finish the sheets first.")

    groups = defaultdict(list)
    for i, c in items.items():
        groups[c["prompt"]].append(i)
    names = list(ratings)
    pairs = {f"{x} vs {y}": agreement(ratings[x], ratings[y], groups.values())
             for k, x in enumerate(names) for y in names[k + 1:]}
    rows = [{**c, "ratings": {n: ratings[n][i] for n in names},
             "rating": round(sum(ratings[n][i] for n in names) / len(names), 4)} for i, c in sorted(items.items())]
    write_jsonl(d / "ratings.jsonl", rows)

    res = project_path("eval/results/rerank_tuning")
    res.mkdir(parents=True, exist_ok=True)
    summary = {"date": date.today().isoformat(), "items": len(items), "prompts": len(groups), "raters": names,
               "agreement": pairs,
               "rating_counts": {n: dict(sorted(Counter(r.values()).items())) for n, r in ratings.items()},
               "mean_by_system": {s: round(sum(r["rating"] for r in rows if r["system"] == s) /
                                           sum(r["system"] == s for r in rows), 3)
                                  for s in sorted({r["system"] for r in rows})}}
    json.dump(summary, open(res / "agreement.json", "w", encoding="utf-8"), indent=2)
    for pair, a in pairs.items():
        print(f"{pair}: Spearman {a['spearman']} overall, {a['spearman_within_prompt']} within a prompt "
              f"({a['prompts_with_within']} prompts) | exact {a['exact']:.0%}, within 1 point {a['within_1']:.0%}")
    print(f"rating counts {summary['rating_counts']} | mean by system {summary['mean_by_system']}")
    print(f"wrote {d / 'ratings.jsonl'} and {res / 'agreement.json'}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompts").add_argument("--force", action="store_true", help="redo prompts.jsonl")
    g = sub.add_parser("generate")
    g.add_argument("--system", required=True, choices=["A", "D"])
    g.add_argument("--ckpt-dir", help="folder with the checkpoints (default: paths.checkpoints)")
    g.add_argument("--out-dir", help="where to write candidates_<system>.jsonl (default: paths.rerank_ratings)")
    sub.add_parser("sheets").add_argument("--force", action="store_true", help="overwrite existing rating sheets")
    sub.add_parser("collect")
    args = p.parse_args()
    cfg = load_config()
    {"prompts": cmd_prompts, "generate": cmd_generate, "sheets": cmd_sheets, "collect": cmd_collect}[args.cmd](cfg, args)


if __name__ == "__main__":
    main()
