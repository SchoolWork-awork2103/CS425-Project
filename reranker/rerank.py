"""Runtime filtering and ranking, with provisional configurable weights.

Weights are not human-tuned yet. All hard filters apply again on every retry.
"""
import math
import re
from pathlib import Path


def tokens(lines):
    return re.findall(r"[a-z]+", " ".join(lines).casefold())


def rouge_l(a, b):
    """Token LCS F1, also used for the history similarity penalty."""
    a, b = tokens(a), tokens(b)
    if not a or not b:
        return 0.0
    row = [0] * (len(b) + 1)
    for x in a:
        previous = 0
        for j, y in enumerate(b, 1):
            old = row[j]
            row[j] = previous + 1 if x == y else max(row[j], row[j - 1])
            previous = old
    return 2 * row[-1] / (len(a) + len(b))


DEFAULT_WEIGHTS = {"logprob": 1.0, "aabb": 2.0, "syllables": 2.0, "lexical": 1.0,
                   "trait_fit": 2.0, "repetition": 1.0, "toxicity": 1.0}


class Reranker:
    def __init__(self, cfg, weights=None, trait_fit=None, toxicity=None, form_fn=None):
        self.cfg, self.trait_fit = cfg, trait_fit
        self.toxicity = toxicity
        self.weights = {**DEFAULT_WEIGHTS, **cfg.get("reranker", {}).get("weights", {}), **(weights or {})}
        self.weights["syllables"] = self.weights["aabb"]
        self.form_fn = form_fn

    def _form(self, lines):
        if self.form_fn:
            return self.form_fn(lines)
        from phonetics import aabb_score, lexical_score, syllable_score
        return {"aabb": aabb_score(lines), "lexical": lexical_score(lines),
                "syllables": syllable_score(lines, **self.cfg.get("diss_form", {}))}

    def _toxicity(self, poems):
        if self.toxicity:
            return self.toxicity(poems)
        if not hasattr(self, "_detoxify"):
            from .toxicity import OfflineToxicity
            root = Path(__file__).resolve().parents[1]
            checkpoint = root / self.cfg["paths"]["toxicity_checkpoint"]
            if not checkpoint.is_file():
                raise FileNotFoundError(f"Missing Detoxify weights: {checkpoint}. See README.md for setup.")
            self._detoxify = OfflineToxicity(checkpoint)
        return self._detoxify(poems)

    def rank(self, traits, candidates, history=()):
        previous = [r.lines if hasattr(r, "lines") else r["lines"] for r in history]
        fingerprints = {tuple(tokens(p)) for p in previous}
        survivors, seen = [], set()
        settings = self.cfg.get("reranker", {})
        for candidate in candidates:
            lines = candidate.get("lines")
            if type(lines) is not list or len(lines) != 4 or any(type(l) is not str or not l.strip() or "\n" in l for l in lines):
                continue
            key = tuple(tokens(lines))
            if key in fingerprints or key in seen:
                continue
            try:
                logprob = float(candidate["norm_logprob"])
                if not math.isfinite(logprob):
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            form = self._form(lines)
            if any(not math.isfinite(form[k]) for k in ("lexical", "aabb", "syllables")):
                continue
            if form["lexical"] < settings.get("lexical_min", 0.8):
                continue
            if settings.get("strict_aabb", True) and form["aabb"] < 1.0:
                continue
            seen.add(key)
            words = tokens(lines)
            bigrams = list(zip(words, words[1:]))
            repetition = 1 - len(set(bigrams)) / max(len(bigrams), 1)
            overlap = max((rouge_l(lines, p) for p in previous), default=0.0)
            repetition += overlap if overlap > settings.get("history_rouge_threshold", 0.5) else 0.0
            survivors.append({**candidate, "norm_logprob": logprob, "features": {**form, "logprob": logprob,
                                                       "repetition": repetition, "trait_fit": 0.0}})
        if not survivors:
            return []
        toxic = self._toxicity(["\n".join(c["lines"]) for c in survivors])
        if len(toxic) != len(survivors):
            raise ValueError("Toxicity scorer returned the wrong number of results")
        limits = self.cfg["toxicity"]
        filtered = []
        for candidate, scores in zip(survivors, toxic):
            if any(k not in scores or not math.isfinite(float(scores[k])) for k in limits):
                raise ValueError("Incomplete toxicity scores")
            if any(float(scores[k]) >= threshold for k, threshold in limits.items()):
                continue
            candidate["features"]["toxicity"] = max(float(scores[k]) for k in limits)
            filtered.append(candidate)
        if not filtered:
            return []
        for name in ("logprob", "aabb", "syllables", "lexical", "repetition", "toxicity"):
            values = [c["features"][name] for c in filtered]
            lo, hi = min(values), max(values)
            for c in filtered:
                c.setdefault("scaled_features", {})[name] = ((c["features"][name] - lo) / (hi - lo) if hi > lo else 0.0)
        def score(candidate):
            f = candidate["scaled_features"]
            return sum(self.weights[k] * f.get(k, 0) * (-1 if k in {"repetition", "toxicity"} else 1)
                       for k in self.weights)

        # Ties on the weighted score fall back to the model's own preference, then text order.
        def rank_key(candidate):
            return (-score(candidate), -candidate["norm_logprob"], tuple(candidate["lines"]))

        filtered.sort(key=rank_key)
        shortlist = filtered[:settings.get("trait_fit_top_k", 5)]
        if traits and self.trait_fit:
            fits = self.trait_fit.score(traits, [c["lines"] for c in shortlist])
            if len(fits) != len(shortlist) or any(not math.isfinite(float(v)) or not 0 <= v <= 1 for v in fits):
                raise ValueError("Invalid trait-fit scores")
            lo, hi = min(fits), max(fits)
            for c, value in zip(shortlist, fits):
                c["features"]["trait_fit"] = float(value)
                c["scaled_features"]["trait_fit"] = (value - lo) / (hi - lo) if hi > lo else 0.0
        for candidate in shortlist:
            candidate["score"] = score(candidate)
        return sorted(shortlist, key=rank_key)
