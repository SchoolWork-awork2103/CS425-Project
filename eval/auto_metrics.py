"""Phase 9: metrics and statistics for the frozen-prompt evaluation (eval/run_auto_eval.py).

Pure functions, no models: the trait-fit and embedding scores are computed by run_auto_eval.py and passed in. The
unit is the prompt: a system's poems for one prompt are not independent of each other, so confidence intervals
resample prompts, and two systems or configurations are compared prompt by prompt (paired).
"""
import random
import re
import statistics

from phonetics import last_word, rhymes, same_sound, words_of


def strict_aabb(lines):
    """Both couplets rhyme (CMUdict) and the A and B rhyme sounds differ: the Phase 9 definition."""
    if len(lines) != 4 or not all(l.strip() for l in lines):
        return False
    e = [last_word(l) for l in lines]
    return rhymes(e[0], e[1]) and rhymes(e[2], e[3]) and not same_sound(e[0], e[2])


def end_word_hit(lines, planned):
    """Share of the four planned end words that end their line."""
    return sum(last_word(l) == w for l, w in zip(lines, planned)) / 4


def trait_terms(traits, info):
    """The traits and their synonyms from traits.json, as report() in qwen_lora.py counts a trait mention."""
    return [t for tr in traits for t in [tr, *info.get(tr, {}).get("synonyms", [])]]


def mentions(lines, terms):
    """True when the poem names a trait or synonym; None for a request with no traits."""
    if not terms:
        return None
    text = " ".join(lines).lower()
    return any(re.search(rf"\b{re.escape(t.lower())}\b", text) for t in terms)


def ngrams(words, n):
    return [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]


def distinct(poems, n):
    """Distinct-n over a set of poems: unique n-grams / all n-grams (within lines). It grows as the set shrinks, so
    compare only sets of the same size."""
    grams = [g for lines in poems for l in lines for g in ngrams(words_of(l), n)]
    return len(set(grams)) / len(grams) if grams else 0.0


def training_ngrams(rows, n=4):
    """The word n-grams of the training disses (over each poem's words in order) and their lines, for memorization."""
    grams, lines = set(), set()
    for r in rows:
        grams.update(ngrams([w for l in r["lines"] for w in words_of(l)], n))
        lines.update(tuple(words_of(l)) for l in r["lines"])
    return grams, lines


def memorization(lines, train_grams, train_lines, n=4):
    """Share of the poem's word n-grams that also occur in a training diss, and whether a whole line is copied."""
    grams = ngrams([w for l in lines for w in words_of(l)], n)
    return {"overlap": sum(g in train_grams for g in grams) / len(grams) if grams else 0.0,
            "copied_line": any(tuple(words_of(l)) in train_lines for l in lines if words_of(l))}


def interleave(by_plan, k):
    """The first k candidates, taking the plans in turn (plan 1's first, plan 2's first, plan 1's second, ...), so
    any k draws evenly from the plans and a smaller k is always a subset of a larger one."""
    out = []
    for i in range(max(map(len, by_plan), default=0)):
        out += [p[i] for p in by_plan if i < len(p)]
    return out[:k]


def choose(batches, rerank, select):
    """The reply the app would give (Pipeline._respond in app/pipeline.py): rerank each generation batch in turn and
    keep the first one select() accepts; select(ranked, last) relaxes its rule on the last batch. Returns the chosen
    candidate (or None), how many batches were used and how many candidates survived the hard filters in the last."""
    for i, batch in enumerate(batches):
        ranked = rerank(batch)
        best = select(ranked, i == len(batches) - 1)
        if best:
            return best, i + 1, len(ranked)
    return None, len(batches), len(ranked) if batches else 0


def first_safe(candidates, toxicity, limits, chunk=5):
    """The first candidate under every toxicity limit, or None: the generator alone, with only the safety filter.
    toxicity(texts) gives one dict of scores per text; candidates are checked a few at a time, in order."""
    for i in range(0, len(candidates), chunk):
        part = candidates[i:i + chunk]
        for c, t in zip(part, toxicity(["\n".join(c["lines"]) for c in part])):
            if all(t[k] < lim for k, lim in limits.items()):
                return c
    return None


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def bootstrap_ci(values, b=2000, seed=0, level=0.95):
    """Mean and percentile interval of per-prompt values, resampling prompts with replacement. None values (a
    metric that does not apply to a prompt) are left out."""
    values = [float(v) for v in values if v is not None]
    if not values:
        return {"mean": None, "low": None, "high": None, "n": 0}
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(b))
    tail = (1 - level) / 2
    return {"mean": sum(values) / len(values), "low": means[int(tail * (b - 1))],
            "high": means[int((1 - tail) * (b - 1))], "n": len(values)}


def paired(a, b, bs=2000, seed=0):
    """a minus b on the same prompts (dicts prompt -> value): the mean difference with a bootstrap interval over
    prompts, and the Wilcoxon signed-rank p-value (None when every difference is 0 or scipy is missing)."""
    keys = [k for k in a if k in b and a[k] is not None and b[k] is not None]
    diffs = [float(a[k]) - float(b[k]) for k in keys]
    res = bootstrap_ci(diffs, bs, seed)
    res["p_wilcoxon"] = None
    if any(diffs):
        try:
            from scipy.stats import wilcoxon
            res["p_wilcoxon"] = float(wilcoxon(diffs).pvalue)
        except (ImportError, ValueError):
            pass
    res["better"], res["worse"] = sum(d > 0 for d in diffs), sum(d < 0 for d in diffs)
    return res


def krippendorff_alpha(units, metric="ordinal"):
    """Krippendorff's alpha for ratings: units[i] is the list of values the raters gave unit i (missing ones left
    out; units with fewer than two values do not count). metric: "nominal", "ordinal" (the default, for 1-5 ratings)
    or "interval". 1 is perfect agreement, 0 is chance."""
    units = [u for u in units if len(u) >= 2]
    values = sorted({v for u in units for v in u})
    index = {v: i for i, v in enumerate(values)}
    size = len(values)
    o = [[0.0] * size for _ in range(size)]                  # coincidence matrix
    for u in units:
        for a in range(len(u)):
            for b in range(len(u)):
                if a != b:
                    o[index[u[a]]][index[u[b]]] += 1 / (len(u) - 1)
    n_c = [sum(row) for row in o]
    n = sum(n_c)

    def delta(c, k):
        if metric == "nominal":
            return float(c != k)
        if metric == "interval":
            return (values[c] - values[k]) ** 2
        lo, hi = min(c, k), max(c, k)
        return (sum(n_c[lo:hi + 1]) - (n_c[c] + n_c[k]) / 2) ** 2

    observed = sum(o[c][k] * delta(c, k) for c in range(size) for k in range(size))
    expected = sum(n_c[c] * n_c[k] * delta(c, k) for c in range(size) for k in range(size)) / (n - 1) if n > 1 else 0
    return 1.0 if expected == 0 else 1 - observed / expected


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values, in the given order (None stays None): controls the chance of any false
    positive across a family of tests."""
    order = sorted((p, i) for i, p in enumerate(pvalues) if p is not None)
    adjusted, running = [None] * len(pvalues), 0.0
    for rank, (p, i) in enumerate(order):
        running = max(running, min(1.0, (len(order) - rank) * p))
        adjusted[i] = running
    return adjusted


def spread(values):
    """Standard deviation over seeds (0 for a single seed)."""
    values = [v for v in values if v is not None]
    return statistics.stdev(values) if len(values) > 1 else 0.0
