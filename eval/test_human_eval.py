"""Human evaluation tests, with no models. Run from the project root:  python -m unittest eval.test_human_eval -v"""
import csv
import tempfile
import unittest
from pathlib import Path

from eval import auto_metrics as M
from eval.human_eval import (COLUMNS, CONFIGS, CRITERIA, MIX, POEM_SEED, analyse_panel, build_items, rater_layout,
                             read_ratings)


def chosen_rows():
    """chosen.jsonl rows: 50 prompts in the frozen mix, every configuration, two seeds."""
    cats = ["single"] * 20 + ["multi"] * 20 + ["heldout"] * 5 + ["unclear"] * 5
    rows = []
    for pid, cat in enumerate(cats, 1):
        for seed in (0, POEM_SEED):
            for system, config in CONFIGS + [("A", "base")]:
                lines = [f"{system} {config} {pid} {seed} line {i}" for i in range(4)]
                if (system, config) == ("E", "full") and pid == 41:
                    lines = [f"D full {pid} {seed} line {i}" for i in range(4)]      # same poem as D-full
                rows.append({"system": system, "config": config, "prompt": pid, "seed": seed, "category": cat,
                             "traits": [] if cat == "unclear" else ["smart"], "intensity": "mild", "lines": lines,
                             "metrics": {"aabb": 1}})
    return rows


class AlphaTest(unittest.TestCase):
    # Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability": 4 observers, 12 units, missing values
    UNITS = [[1, 1, 1], [2, 2, 3, 2], [3, 3, 3, 3], [3, 3, 3, 3], [2, 2, 2, 2], [1, 2, 3, 4], [4, 4, 4, 4],
             [1, 1, 2, 1], [2, 2, 2, 2], [5, 5, 5], [1, 1], [3]]

    def test_published_values(self):
        self.assertAlmostEqual(M.krippendorff_alpha(self.UNITS, "nominal"), 0.743, places=3)
        self.assertAlmostEqual(M.krippendorff_alpha(self.UNITS, "ordinal"), 0.815, places=3)
        self.assertAlmostEqual(M.krippendorff_alpha(self.UNITS, "interval"), 0.849, places=3)

    def test_perfect_agreement(self):
        self.assertEqual(M.krippendorff_alpha([[1, 1], [3, 3], [5, 5]]), 1.0)

    def test_holm(self):
        self.assertEqual(M.holm([0.01, None, 0.04, 0.03]), [0.03, None, 0.06, 0.06])


class FormsTest(unittest.TestCase):
    def test_items(self):
        selected, items, practice, missing = build_items(chosen_rows(), seed=42)
        cats = {pid: ("single" if pid <= 20 else "multi" if pid <= 40 else "heldout" if pid <= 45 else "unclear")
                for pid in selected}
        self.assertEqual({c: list(cats.values()).count(c) for c in MIX}, MIX)
        self.assertEqual(missing, [])
        self.assertTrue(all(it["lines"][0].split()[3] == str(POEM_SEED) for it in items))     # the seed-425 poems
        shared = [it for it in items if len(it["configs"]) > 1]
        self.assertEqual([it["configs"] for it in shared], [["D-full", "E-full"]])            # prompt 41 (held out)
        self.assertEqual(len(items), len(CONFIGS) * 30 - 1)
        self.assertEqual(sorted(it["item"] for it in items), list(range(1, len(items) + 1)))
        self.assertNotIn(practice["prompt"], selected)
        self.assertEqual(build_items(chosen_rows(), seed=42)[1], items)                       # fixed by the seed

    def test_layout(self):
        selected, items, _, _ = build_items(chosen_rows(), seed=42)
        one, two = rater_layout(items, selected, 1, 42), rater_layout(items, selected, 2, 42)
        self.assertEqual([len(p) for p in one], [10, 10, 10])
        titles = lambda parts: sorted(p["title"] for part in parts for r in part for p in r["poems"])
        self.assertEqual(titles(one), titles(two))                    # every rater rates every poem ...
        order = lambda parts: [r["request"] + str(r["poems"][0]["title"]) for part in parts for r in part]
        self.assertNotEqual(order(one), order(two))                   # ... in their own order
        self.assertNotIn("D-full", str(one))                          # blind: no configuration names

    def test_read_ratings(self):
        items = {1: {}, 2: {}, 3: {}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rater.csv"
            with open(path, "w", encoding="utf-8", newline="") as f:  # an LLM sheet: extra columns, unpadded number
                csv.writer(f).writerows([["poem", "line1", *COLUMNS], ["1", "a, b", 3, 4, 2, 1, 5],
                                         ["002", "c", 3, 4, 2, 1, 6], ["2", "c", 3, 4, 2, 1, 5]])
            got, problems = read_ratings(path, items)
        self.assertEqual(got[1], dict(zip(CRITERIA, [3, 4, 2, 1, 5])))
        self.assertEqual(problems, ["rater.csv poem 002 rhyme: '6', not 1-5", "rater.csv: poem 002 rated twice",
                                    "rater.csv: poem 003 missing"])

    def test_panel(self):
        items = {i: {"prompt": p, "configs": [c], "category": "heldout" if p == 1 else "single"}
                 for i, (p, c) in enumerate([(p, f"{s}-{k}") for p in (1, 2, 3) for s, k in CONFIGS], 1)}
        rate = lambda bump: {i: {c: 2 + 2 * (it["configs"][0] == "D-full") + bump for c in CRITERIA}
                             for i, it in items.items()}
        panel = analyse_panel({"r1": rate(0), "r2": rate(1)}, items, bootstrap=100)
        self.assertEqual(panel["results"]["D-full"]["Humour"]["mean"], 4.5)
        self.assertEqual(panel["results"]["D-base"]["Humour"]["heldout"], 2.5)
        self.assertEqual(panel["comparisons"]["D-full vs D-base"]["Rhyme"]["mean"], 2.0)
        self.assertEqual(panel["flat_raters"], {})
        flat = {i: {c: 3 for c in CRITERIA} for i in items}                # the same score everywhere
        self.assertEqual(set(analyse_panel({"r1": rate(0), "r3": flat}, items, 100)["flat_raters"]), {"r3"})
        self.assertIsNone(analyse_panel({"r1": rate(0)}, items, 100)["agreement_alpha_ordinal"]["Rhyme"])


if __name__ == "__main__":
    unittest.main()
