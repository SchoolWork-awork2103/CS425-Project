import unittest
from unittest.mock import Mock
from .rerank import Reranker, rouge_l
from utils import load_config

GOOD = ["you call yourself confident and proud,", "but all we hear is you being loud.",
        "you think your every word is wise,", "yet nobody listens, we just roll our eyes."]


class RerankerTest(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.toxicity = Mock(side_effect=lambda poems: [{k: 0.0 for k in self.cfg["toxicity"]} for p in poems])
        self.reranker = Reranker(self.cfg, toxicity=self.toxicity)

    def test_format_rhyme_lexical_and_history_filters(self):
        candidates = [{"lines": GOOD[:3], "norm_logprob": -1},
                      {"lines": ["unknownxyz word"] * 4, "norm_logprob": -1},
                      {"lines": ["a dog", "a cat", "a bird", "a fish"], "norm_logprob": -1},
                      {"lines": GOOD, "norm_logprob": float("nan")},
                      {"lines": GOOD, "norm_logprob": -1}]
        ranked = self.reranker.rank(["confident"], candidates)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(self.reranker.rank([], candidates, [{"lines": GOOD}]), [])

    def test_toxicity_is_hard_filter_and_missing_scores_fail_closed(self):
        self.toxicity.side_effect = lambda poems: [{k: 1.0 for k in self.cfg["toxicity"]} for p in poems]
        self.assertEqual(self.reranker.rank([], [{"lines": GOOD, "norm_logprob": -1}]), [])
        self.toxicity.side_effect = lambda poems: [{} for p in poems]
        with self.assertRaises(ValueError):
            self.reranker.rank([], [{"lines": GOOD, "norm_logprob": -1}])

    def test_trait_fit_only_on_top_five_and_constant_features_are_finite(self):
        form = lambda lines: {"aabb": 1.0, "lexical": 1.0, "syllables": 1.0}
        fit = Mock()
        fit.score.return_value = [0.1, 0.2, 0.3, 0.9, 0.4]
        reranker = Reranker(self.cfg, toxicity=self.toxicity, form_fn=form, trait_fit=fit)
        candidates = [{"lines": [f"version {word}", *GOOD[1:]], "norm_logprob": -i - 1}
                      for i, word in enumerate(["one", "two", "three", "four", "five", "six"])]
        ranked = reranker.rank(["confident"], candidates)
        self.assertEqual(len(fit.score.call_args.args[1]), 5)
        self.assertEqual(ranked[0]["features"]["trait_fit"], 0.9)
        self.assertEqual(rouge_l(GOOD, GOOD), 1.0)


if __name__ == "__main__":
    unittest.main()
