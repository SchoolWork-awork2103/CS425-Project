"""Phase 2 unit tests. Run from the project root:  python -m unittest phonetics.test_phonetics -v"""
import json, sys, unittest
from pathlib import Path

from utils import load_config, project_path
from phonetics import (aabb_score, lexical_score, line_syllables, near_rhyme, rhymes, same_sound, syllable_score,
                       word_syllables)

RHYME = [("late", "wait"), ("phone", "alone"), ("air", "chair"), ("one", "done"), ("in", "grin"), ("red", "spread"),
         ("trace", "grace"), ("up", "cup"), ("proud", "loud"), ("wise", "eyes"), ("cheap", "keep"), ("smart", "heart"),
         ("elevate", "fate"), ("doormat", "chat"), ("approach", "cockroach"), ("deadline", "design"),
         ("funny", "money"), ("lazy", "crazy")]
NO_RHYME = [("late", "phone"), ("play", "replay"), ("side", "inside"), ("way", "away"), ("one", "won"),
            ("happy", "me"), ("water", "later"), ("time", "mine"), ("proud", "pride"), ("cat", "cat"),
            ("love", "move"), ("xyzzyq", "fizzy")]                  # eye rhyme; unknown word


class RhymeTest(unittest.TestCase):
    def test_rhymes(self):
        for a, b in RHYME:
            self.assertTrue(rhymes(a, b), (a, b))
            self.assertTrue(rhymes(b, a), (b, a))

    def test_not_rhymes(self):
        for a, b in NO_RHYME:
            self.assertFalse(rhymes(a, b), (a, b))

    def test_near_rhyme(self):
        self.assertTrue(near_rhyme("time", "mine"))
        self.assertTrue(near_rhyme("home", "alone"))
        self.assertFalse(near_rhyme("cat", "hat"))        # a full rhyme is not "near"
        self.assertFalse(near_rhyme("cat", "dog"))

    def test_same_sound(self):
        self.assertTrue(same_sound("proud", "loud"))
        self.assertFalse(same_sound("proud", "wise"))

    def test_syllables(self):
        self.assertEqual(word_syllables("roast"), 1)
        self.assertEqual(word_syllables("confident"), 3)
        self.assertEqual(line_syllables("you think you're so proud"), 5)
        self.assertGreaterEqual(word_syllables("blorptastic"), 2)      # unknown word: vowel-group estimate


class ScoreTest(unittest.TestCase):
    GOOD = ["you call yourself confident and proud,", "but all we hear is you being loud.",
            "you think your every word is wise,", "yet nobody listens, we just roll our eyes."]

    def test_aabb(self):
        self.assertEqual(aabb_score(self.GOOD), 1.0)
        near = self.GOOD[:2] + ["you think you have the perfect time,", "but all you do is waste mine."]
        self.assertEqual(aabb_score(near), 0.75)                         # one exact, one near
        aaaa = self.GOOD[:2] + ["you say it all with so much pride, crowd", "then hide away behind a cloud"]
        self.assertLess(aabb_score(aaaa), 1.0)                           # A and B on the same sound
        self.assertEqual(aabb_score(self.GOOD[:3]), 0.0)
        self.assertEqual(aabb_score(["a dog", "a cat", "a bird", "a fish"]), 0.0)

    def test_syllables(self):
        self.assertEqual(syllable_score(self.GOOD), 1.0)
        short = ["you", "are", "so", "proud"]
        self.assertLess(syllable_score(short), 0.6)
        unbalanced = ["no", "but all we ever hear from you is just how loud you are", *self.GOOD[2:]]
        self.assertLess(syllable_score(unbalanced), 1.0)

    def test_lexical(self):
        self.assertEqual(lexical_score(self.GOOD), 1.0)
        self.assertLess(lexical_score("you blorptastic zingwomp"), 0.5)
        self.assertEqual(lexical_score("you blorptastic", vocab={"blorptastic"}), 1.0)


class DataAgreementTest(unittest.TestCase):
    """The module must judge rhyme exactly like data/form_checks.py, which filtered the training data."""

    def test_matches_form_checks(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))
        import form_checks
        cfg = load_config()
        words = set()
        for path in (project_path(cfg["paths"]["corpus_dir"]) / "quatrains_train.jsonl",
                     project_path(cfg["paths"]["diss_dir"]) / "train.jsonl"):
            for line in open(path, encoding="utf-8"):
                r = json.loads(line)
                for a, b in r["rhymes"]:
                    self.assertTrue(rhymes(a, b), (a, b))               # every training couplet rhymes
                    words |= {a, b}
        words = sorted(words)[:600]
        for a in words[:60]:                                             # and agree on arbitrary pairs
            for b in words:
                self.assertEqual(rhymes(a, b), form_checks.rhymes(a, b), (a, b))


@unittest.skipUnless(Path(str(project_path(load_config()["paths"]["glove"])) + ".npy").exists(),
                     "GloVe not prepared (data/prepare_glove.py)")
class PlannerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from phonetics.planner import RhymePlanner
        cls.planner = RhymePlanner()

    def check_plan(self, plan):
        (a1, a2), (b1, b2) = plan["pairs"]
        self.assertTrue(rhymes(a1, a2) and rhymes(b1, b2), plan)
        self.assertFalse(same_sound(a1, b1), plan)
        self.assertEqual(len(set(plan["end_words"])), 4, plan)

    def test_every_trait(self):
        for trait in self.planner.traits:
            plans = self.planner.plan([trait], k=3)
            self.assertEqual(len(plans), 3, trait)
            for p in plans:
                self.check_plan(p)
                self.assertFalse(set(p["end_words"]) & self.planner.avoid, p)

    def test_multi_unknown_and_none(self):
        for traits in (["confident", "funny"], ["tidy", "ambitious", "loyal"], ["xyzzyq"], []):
            plans = self.planner.plan(traits, k=3)
            self.assertTrue(plans, traits)
            for p in plans:
                self.check_plan(p)

    def test_exclude(self):
        first = self.planner.plan(["lazy"], k=1)[0]["end_words"]
        for p in self.planner.plan(["lazy"], k=3, exclude=first):
            self.assertFalse(set(p["end_words"]) & set(first), p)


if __name__ == "__main__":
    unittest.main()
