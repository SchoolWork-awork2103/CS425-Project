"""Reranker filters, history and trait-fit order, with Detoxify and DistilBERT stubbed out: python -m unittest reranker.test_rerank"""
import unittest
from unittest.mock import Mock
from .rerank import Reranker, rouge_l
from utils import load_config

GOOD = ["you call yourself confident and proud,", "but all we hear is you being loud.",
        "you think your every word is wise,", "yet nobody listens, we just roll our eyes."]


def stub(cfg, score=0.0, fit=None):
    rr = Reranker(cfg, trait_fit=fit is not None)
    rr.toxicity = lambda poems: [{k: score for k in cfg["toxicity"]} for _ in poems]
    rr._fit = fit
    return rr


class RerankerTest(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()

    def test_hard_filters(self):
        candidates = [{"lines": GOOD[:3], "norm_logprob": -1},
                      {"lines": ["unknownxyz qwertyzz"] * 4, "norm_logprob": -1},
                      {"lines": GOOD, "norm_logprob": -1}]
        ranked = stub(self.cfg).rerank(["confident"], candidates)
        self.assertEqual([c["lines"] for c in ranked], [GOOD])
        self.assertEqual(stub(self.cfg, score=1.0).rerank([], candidates), [])

    def test_history_drops_repeats_and_penalizes_overlap(self):
        close = [*GOOD[:3], "yet nobody listens, we all roll our eyes."]
        candidates = [{"lines": GOOD, "norm_logprob": -1}, {"lines": close, "norm_logprob": -1}]
        ranked = stub(self.cfg).rerank([], candidates, history=[{"lines": GOOD}])
        self.assertEqual([c["lines"] for c in ranked], [close])
        self.assertGreater(ranked[0]["features"]["history"], self.cfg["reranker"]["history_rouge"])
        alone = stub(self.cfg).rerank([], [{"lines": close, "norm_logprob": -1}])
        self.assertAlmostEqual(alone[0]["score"] - ranked[0]["score"], ranked[0]["features"]["history"])
        self.assertEqual(rouge_l(GOOD, GOOD), 1.0)
        self.assertEqual(rouge_l(GOOD, []), 0.0)

    def test_trait_fit_only_on_the_top_candidates(self):
        fit = Mock()
        fit.score.side_effect = lambda traits, poems: [0.9 if p[0].startswith("version six") else 0.1 for p in poems]
        candidates = [{"lines": [f"version {w} {GOOD[0]}", *GOOD[1:]], "norm_logprob": -i - 1}
                      for i, w in enumerate(["one", "two", "three", "four", "five", "six", "seven"])]
        ranked = stub(self.cfg, fit=fit).rerank(["confident"], candidates)
        self.assertEqual(len(fit.score.call_args.args[1]), self.cfg["reranker"]["trait_fit_top"])
        self.assertTrue(all("trait_fit" not in c["features"] for c in ranked[self.cfg["reranker"]["trait_fit_top"]:]))


if __name__ == "__main__":
    unittest.main()
