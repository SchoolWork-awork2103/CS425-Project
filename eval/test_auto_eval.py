"""Frozen-prompt evaluation tests, with no models. Run from the project root:  python -m unittest eval.test_auto_eval -v"""
import unittest

from eval import auto_metrics as M
from eval.run_auto_eval import config_batches

GOOD = ["you call yourself smart and always so bright,", "but your ideas never once see the light.",
        "you say ambition is what keeps you alive,", "yet you nap through the day with no drive."]


class FormTest(unittest.TestCase):
    def test_strict_aabb(self):
        self.assertTrue(M.strict_aabb(GOOD))
        self.assertFalse(M.strict_aabb(GOOD[:3]))
        self.assertFalse(M.strict_aabb([GOOD[0], GOOD[1], GOOD[2], "yet you nap through the day."]))
        same = [GOOD[0], GOOD[1], "you think you are right,", "but you lose every fight."]
        self.assertFalse(M.strict_aabb(same))                      # A and B on one sound read as AAAA

    def test_end_word_hit(self):
        self.assertEqual(M.end_word_hit(GOOD, ["bright", "light", "alive", "drive"]), 1.0)
        self.assertEqual(M.end_word_hit(GOOD, ["bright", "night", "alive", "thrive"]), 0.5)

    def test_mentions(self):
        info = {"smart": {"synonyms": ["clever", "brainy"]}}
        self.assertTrue(M.mentions(GOOD, M.trait_terms(["smart"], info)))
        self.assertFalse(M.mentions(["you are lazy and slow"], M.trait_terms(["smart"], info)))
        self.assertIsNone(M.mentions(GOOD, []))


class TextTest(unittest.TestCase):
    def test_distinct(self):
        self.assertEqual(M.distinct([["a b a b"]], 1), 0.5)
        self.assertEqual(M.distinct([["a b", "a b"]], 2), 0.5)     # n-grams stay within a line

    def test_memorization(self):
        grams, lines = M.training_ngrams([{"lines": ["you call yourself smart and always so bright,", "x y"]}])
        m = M.memorization(GOOD, grams, lines)
        self.assertTrue(m["copied_line"])
        self.assertGreater(m["overlap"], 0)
        self.assertLess(m["overlap"], 1)
        self.assertEqual(M.memorization(["one two three"], grams, lines), {"overlap": 0.0, "copied_line": False})


class SelectionTest(unittest.TestCase):
    def test_interleave_nested(self):
        by_plan = [["a1", "a2", "a3"], ["b1", "b2"]]
        self.assertEqual(M.interleave(by_plan, 3), ["a1", "b1", "a2"])
        self.assertEqual(M.interleave(by_plan, 10), ["a1", "b1", "a2", "b2", "a3"])
        for k in range(1, 5):                                       # a smaller k is a prefix of a larger one
            self.assertEqual(M.interleave(by_plan, k), M.interleave(by_plan, k + 1)[:k])

    def test_choose_relaxes_on_last_batch(self):
        rerank = lambda batch: sorted(batch, key=lambda c: -c["score"])
        select = lambda ranked, last: next((c for c in ranked if c["aabb"]), ranked[0] if last and ranked else None)
        weak = [{"score": 2, "aabb": False}]
        good = [{"score": 1, "aabb": True}]
        self.assertEqual(M.choose([weak, good], rerank, select), (good[0], 2, 1))
        self.assertEqual(M.choose([weak, weak], rerank, select), (weak[0], 2, 1))
        self.assertEqual(M.choose([[], []], rerank, select), (None, 2, 0))

    def test_first_safe(self):
        cands = [{"lines": [f"poem {i}"]} for i in range(7)]
        scores = {"poem 0": 0.9, "poem 1": 0.8, "poem 6": 0.0}
        toxicity = lambda texts: [{"threat": scores.get(t, 0.5)} for t in texts]
        self.assertIs(M.first_safe(cands, toxicity, {"threat": 0.6}, chunk=2), cands[2])
        self.assertIs(M.first_safe(cands, toxicity, {"threat": 0.1}, chunk=5), cands[6])    # found in the 2nd chunk
        self.assertIsNone(M.first_safe(cands, toxicity, {"threat": 0.0}))

    def test_config_batches(self):
        row = {"plans": [["p"] * 4, ["q"] * 4],
               "candidates": [{"plan": j, "batch": b, "sample": i, "lines": [], "norm_logprob": 0}
                              for j in range(2) for b in range(2) for i in range(3)]}
        full = config_batches(row, "full", 2)
        self.assertEqual([len(b) for b in full], [6, 6])
        self.assertTrue(all(c["batch"] == 0 for c in full[0]))
        self.assertEqual(full[0][0]["planned_end_words"], ["p"] * 4)
        k4 = config_batches(row, "k4", 2)[0]
        self.assertEqual([(c["plan"], c["batch"], c["sample"]) for c in k4], [(0, 0, 0), (1, 0, 0), (0, 0, 1), (1, 0, 1)])


class StatsTest(unittest.TestCase):
    def test_bootstrap(self):
        ci = M.bootstrap_ci([0, 1, 1, 1, None], b=500, seed=1)
        self.assertEqual((ci["mean"], ci["n"]), (0.75, 4))
        self.assertTrue(0 <= ci["low"] <= ci["mean"] <= ci["high"] <= 1)
        self.assertEqual(ci, M.bootstrap_ci([0, 1, 1, 1], b=500, seed=1))
        self.assertIsNone(M.bootstrap_ci([None])["mean"])

    def test_paired(self):
        r = M.paired({1: 1, 2: 1, 3: 0, 4: None}, {1: 0, 2: 1, 3: 0, 5: 1}, bs=200)
        self.assertEqual((r["n"], r["better"], r["worse"]), (3, 1, 0))
        self.assertAlmostEqual(r["mean"], 1 / 3)


if __name__ == "__main__":
    unittest.main()
