"""Phase 5: the reranker. Picks the best of a generator's candidates for one request.

    score = w1·logprob + w2·aabb + w3·syllables + w4·lexical + w5·trait_fit − w6·repetition − w7·toxicity

Every feature is in [0, 1]. logprob is the length-normalized log-probability, min-max scaled over the request's
candidates (A's and D's are on different scales, and only the order within a request matters). w3 is tied to w2
unless set: almost every candidate scores 1 on syllables, so the ratings can't tune it (pipeline.md, Phase 5).

Order, as in pipeline.md: the hard filters (four lines, lexical_score >= reranker.lexical_min, under every Detoxify
limit in `toxicity`), then the instant features on all candidates, then DistilBERT trait fit on the top
reranker.trait_fit_top only. Weights are reranker.weights in config.yaml.

    rr = Reranker()
    ranked = rr.rerank(["confident"], candidates)    # candidates: generate() output, dicts with lines, norm_logprob
    ranked[0]["lines"]                               # the reply; each kept candidate has "score" and "features"
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "data" / "disses")]
from utils import load_config, project_path
from phonetics import aabb_score, lexical_score, syllable_score, words_of
from phonetics.planner import STOP

INSTANT = ("logprob", "aabb", "syllables", "lexical", "repetition", "toxicity")


def repetition(lines):
    """Share of content words that repeat an earlier one in the poem ("your planner ... or planner")."""
    ws = [w for l in lines for w in words_of(l) if len(w) >= 3 and w not in STOP]
    return 1 - len(set(ws)) / len(ws) if ws else 0.0


def scaled(values):
    """Min-max over one request's candidates; all the same gives 0.5 (no effect on the order)."""
    lo, hi = min(values), max(values)
    return [0.5 if hi == lo else (v - lo) / (hi - lo) for v in values]


def combine(f, w):
    """The weighted score of one candidate's features. trait_fit counts only once it has been computed."""
    syl = w.get("syllables", w["aabb"])                      # tied to the rhyme weight unless set
    return (w["logprob"] * f["logprob"] + w["aabb"] * f["aabb"] + syl * f["syllables"] + w["lexical"] * f["lexical"]
            + w["trait_fit"] * f.get("trait_fit", 0.0) - w["repetition"] * f["repetition"]
            - w["toxicity"] * f["toxicity"])


class Reranker:
    def __init__(self, cfg=None, weights=None, device="cpu", trait_fit=True):
        self.cfg = cfg or load_config()
        r = self.cfg["reranker"]
        self.weights = {**r["weights"], **(weights or {})}
        self.lexical_min, self.top = r["lexical_min"], r["trait_fit_top"]
        self.limits = self.cfg["toxicity"]
        vocab = Path(f"{project_path(self.cfg['paths']['glove'])}.vocab.txt")
        self.vocab = set(vocab.read_text(encoding="utf-8").split("\n")) if vocab.exists() else None
        self._detox, self._fit, self.device, self.use_fit = None, None, device, trait_fit

    def toxicity(self, poems):
        """Detoxify scores for the limited categories, one dict per poem."""
        if self._detox is None:
            from detoxify import Detoxify                    # ~400 MB, loaded on first use
            self._detox = Detoxify("original", device=self.device)
        out = self._detox.predict(poems)                     # a batch of one gives floats instead of lists
        return [{k: float(out[k][i] if isinstance(out[k], list) else out[k]) for k in self.limits}
                for i in range(len(poems))]

    def trait_fit(self, traits, poems):
        """P(the poem roasts the traits). A request with no traits gets 0.5 for all (no effect on the order)."""
        if not traits or not poems:
            return [0.5] * len(poems)
        if self._fit is None:
            from reranker.trait_fit import TraitFit
            self._fit = TraitFit.load(device=self.device)
        return self._fit.score(traits, poems)

    def features(self, candidates, tox=None):
        """Instant features of candidates that passed the hard filters; logprob scaled over this set."""
        tox = tox or self.toxicity(["\n".join(c["lines"]) for c in candidates])
        lp = scaled([c["norm_logprob"] for c in candidates])
        return [{"logprob": l, "aabb": aabb_score(c["lines"]), "syllables": syllable_score(c["lines"]),
                 "lexical": lexical_score(c["lines"], self.vocab), "repetition": repetition(c["lines"]),
                 "toxicity": max(t.values())} for c, l, t in zip(candidates, lp, tox)]

    def filter(self, candidates):
        """(kept candidates with their toxicity scores, dropped candidates with a reason)."""
        four = [c for c in candidates if len(c["lines"]) == 4 and all(l.strip() for l in c["lines"])]
        dropped = [{**c, "dropped": "not_4_lines"} for c in candidates if c not in four]
        tox = self.toxicity(["\n".join(c["lines"]) for c in four]) if four else []
        kept = []
        for c, t in zip(four, tox):
            over = [k for k, lim in self.limits.items() if t[k] >= lim]
            if over:
                dropped.append({**c, "dropped": "toxicity:" + over[0]})
            elif lexical_score(c["lines"], self.vocab) < self.lexical_min:
                dropped.append({**c, "dropped": "lexical"})
            else:
                kept.append((c, t))
        return kept, dropped

    def rerank(self, traits, candidates):
        """Kept candidates, best first, each with "score" and "features". Empty if every candidate was dropped."""
        kept, _ = self.filter(candidates)
        if not kept:
            return []
        cands, tox = [c for c, _ in kept], [t for _, t in kept]
        feats = self.features(cands, tox)
        ranked = sorted(({**c, "features": f, "score": combine(f, self.weights)} for c, f in zip(cands, feats)),
                        key=lambda c: -c["score"])
        if self.use_fit and self.weights["trait_fit"]:
            head = ranked[:self.top]                         # DistilBERT on the top few only
            for c, p in zip(head, self.trait_fit(traits, [c["lines"] for c in head])):
                c["features"]["trait_fit"] = p
                c["score"] = combine(c["features"], self.weights)
            ranked = sorted(head, key=lambda c: -c["score"]) + ranked[self.top:]
        return ranked
