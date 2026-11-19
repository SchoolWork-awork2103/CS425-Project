"""Phase 5 step 5: the reranker weights against the hand ratings (reranker/rating_pool.py collect -> ratings.jsonl).

Only the order within a request matters, so a prompt counts only if its mean ratings are not all equal. Two measures
per prompt, averaged over those prompts:
  spearman  rank correlation of the combined score with the mean rating
  top       mean rating of the candidate the score ranks first; a random pick gets the prompt's mean rating
Compared: equal weights (config.yaml), each feature alone, and a grid search with 5-fold cross-validation over prompts
(weights picked on four folds, scored on the fifth), so the grid's number is not the one it was picked on.

    python reranker/tune_weights.py     # -> eval/results/rerank_tuning/tuning.json
"""
import itertools, json, random, sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "reranker")]
from scipy.stats import spearmanr
from utils import load_config, project_path
from rerank import Reranker, combine, scaled

GRID = {"logprob": [0, 0.5, 1, 2], "aabb": [0, 0.5, 1, 2], "trait_fit": [0, 0.5, 1, 2], "lexical": [0, 1],
        "repetition": [0, 1], "toxicity": [1]}
FOLDS = 5


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def evaluate(groups, w):
    """Mean within-prompt Spearman and mean rating of the top-scored candidate, over the prompts given."""
    rho, top = [], []
    for g in groups:
        s = [combine(c["features"], w) for c in g]
        r = [c["rating"] for c in g]
        x = spearmanr(s, r)[0] if len(set(s)) > 1 else 0.0       # a score that ties everything says nothing
        rho.append(x)
        best = max(s)
        top.append(sum(c["rating"] for c, v in zip(g, s) if v == best) / s.count(best))   # ties: their mean
    return {"spearman": sum(rho) / len(rho), "top": sum(top) / len(top)}


def main():
    cfg = load_config()
    d = project_path(cfg["paths"]["rerank_ratings"])
    rows = read_jsonl(d / "ratings.jsonl")
    prompts = {p["id"]: p for p in read_jsonl(d / "prompts.jsonl")}
    pool = defaultdict(list)                                    # every candidate's log-prob, for the scaling
    for s in cfg["reranker"]["tuning"]["prompts"]:
        for c in read_jsonl(d / f"candidates_{s}.jsonl"):
            pool[c["prompt"]].append(c["norm_logprob"])

    rr = Reranker(cfg)
    by_prompt = defaultdict(list)
    for r in rows:
        by_prompt[r["prompt"]].append(r)
    for pid, g in by_prompt.items():
        feats = rr.features(g, tox=[r["toxicity"] for r in g])
        lp = scaled(pool[pid] + [r["norm_logprob"] for r in g])[-len(g):]   # scaled over the prompt's whole pool
        fit = rr.trait_fit(prompts[pid]["traits"], [r["lines"] for r in g])
        for r, f, l, p in zip(g, feats, lp, fit):
            r["features"] = {**f, "logprob": l, "toxicity": max(v for k, v in r["toxicity"].items() if k in rr.limits),
                             "trait_fit": p}

    groups = [g for g in by_prompt.values() if len({c["rating"] for c in g}) > 1]
    flat = len(by_prompt) - len(groups)
    base = {"random": sum(sum(c["rating"] for c in g) / len(g) for g in groups) / len(groups),
            "best_possible": sum(max(c["rating"] for c in g) for g in groups) / len(groups)}
    equal = dict(cfg["reranker"]["weights"])
    zero = {**{k: 0.0 for k in equal}, "syllables": 0.0}
    # repetition and toxicity are penalties: alone, a lower value ranks higher
    alone = {k: evaluate(groups, {**zero, k: 1.0})
             for k in ("logprob", "aabb", "syllables", "lexical", "trait_fit", "repetition", "toxicity")}

    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    combos = [w for w in combos if any(w[k] for k in ("logprob", "aabb", "trait_fit", "lexical"))]
    rng = random.Random(cfg["seed"])
    order = groups[:]
    rng.shuffle(order)
    folds = [order[k::FOLDS] for k in range(FOLDS)]
    cv, cv_equal, picked = [], [], []
    for k in range(FOLDS):
        train = [g for j, f in enumerate(folds) if j != k for g in f]
        best = max(combos, key=lambda w: evaluate(train, w)["spearman"])
        picked.append(best)
        cv.append(evaluate(folds[k], best))
        cv_equal.append(evaluate(folds[k], equal))
    mean = lambda xs, key: sum(x[key] for x in xs) / len(xs)
    full_best = max(combos, key=lambda w: evaluate(groups, w)["spearman"])

    res = {"date": date.today().isoformat(), "items": len(rows), "prompts": len(by_prompt),
           "prompts_used": len(groups), "prompts_all_one_rating": flat, "baselines": base,
           "equal_weights": {"weights": equal, **evaluate(groups, equal)}, "feature_alone": alone,
           "cv": {"folds": FOLDS, "grid": {"spearman": mean(cv, "spearman"), "top": mean(cv, "top")},
                  "equal_weights": {"spearman": mean(cv_equal, "spearman"), "top": mean(cv_equal, "top")},
                  "picked_per_fold": picked},
           "grid_best_on_all": {"weights": full_best, **evaluate(groups, full_best)}}
    out = project_path("eval/results/rerank_tuning")
    out.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(out / "tuning.json", "w", encoding="utf-8"), indent=2)

    print(f"{len(groups)} of {len(by_prompt)} prompts have different ratings within them ({flat} are all one rating)")
    print(f"mean rating of the pick: random {base['random']:.2f}, best possible {base['best_possible']:.2f}\n")
    print(f"{'':26s}{'spearman':>10s}{'top pick':>10s}")
    print(f"{'equal weights':26s}{res['equal_weights']['spearman']:>10.3f}{res['equal_weights']['top']:>10.2f}")
    for k, v in alone.items():
        print(f"{k + ' alone':26s}{v['spearman']:>10.3f}{v['top']:>10.2f}")
    print(f"{'grid, cross-validated':26s}{res['cv']['grid']['spearman']:>10.3f}{res['cv']['grid']['top']:>10.2f}")
    print(f"{'equal, same folds':26s}{res['cv']['equal_weights']['spearman']:>10.3f}{res['cv']['equal_weights']['top']:>10.2f}")
    print(f"{'grid best on all (biased)':26s}{res['grid_best_on_all']['spearman']:>10.3f}{res['grid_best_on_all']['top']:>10.2f}")
    print("\nweights picked per fold:")
    for w in picked:
        print("  ", w)
    print(f"wrote {out / 'tuning.json'}")


if __name__ == "__main__":
    main()
