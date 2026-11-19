"""System E unit tests, with no model download. Run from the project root:  python -m unittest generation.test_gpt2_lm -v"""
import json, re, unittest

import torch

from utils import load_config, project_path
from generation.gpt2_lm import (STAGE_FILES, AnswerRepetitionPenalty, FourLineStop, answer_text, decode_lines, encode,
                                encode_all, epoch_history, load_split, make_collate, prompt_text, read_jsonl)

WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")
LINES = ["you think you are so very bright,", "yet copy answers every night.",
         "you promised work would be your art,", "then missed the deadline at the start."]
ENDS = ["bright", "night", "art", "start"]


class CharTok:
    """Stands in for the GPT-2 tokenizer: one token per character."""
    eos_token_id, pad_token_id = 0, 0

    def encode(self, text, add_special_tokens=False):
        return [ord(c) for c in text]

    def batch_decode(self, ids, skip_special_tokens=False):
        return ["".join(chr(i) for i in row if i or not skip_special_tokens) for row in ids.tolist()]


class FormatTest(unittest.TestCase):
    def test_prompt(self):
        self.assertEqual(prompt_text(["lazy", "funny"], "harsh", ENDS),
                         "Traits: lazy, funny\nIntensity: harsh\nRhymes: bright night art start\nPoem:\n")
        self.assertTrue(prompt_text([], "none", ENDS).startswith("Traits: none\nIntensity: none\n"))

    def test_answer_round_trip(self):
        text = answer_text(LINES, ENDS)
        self.assertEqual(text.split("\n")[0], "[bright] you think you are so very bright,")
        self.assertEqual(decode_lines(text), LINES)

    def test_decode_lines(self):
        text = "[a] one\n\nno tag here\n[c]   three\n[d] four\n[e] five"
        self.assertEqual(decode_lines(text), ["one", "no tag here", "three", "four"])


class ExampleTest(unittest.TestCase):
    def test_loss_on_completion_only(self):
        e = encode(CharTok(), "ab", "cd", max_len=10)
        self.assertEqual(e["input_ids"], [97, 98, 99, 100, 0])
        self.assertEqual(e["labels"], [-100, -100, 99, 100, 0])
        self.assertEqual(e["attention_mask"], [1] * 5)

    def test_long_example_skipped(self):
        self.assertIsNone(encode(CharTok(), "ab", "cd", max_len=4))     # 5 tokens with the end token
        examples, skipped = encode_all(CharTok(), [("ab", "cd"), ("a", "b")], max_len=4)
        self.assertEqual((len(examples), skipped), (1, 1))
        with self.assertRaises(ValueError):
            encode_all(CharTok(), [("ab", "cd")], max_len=4)

    def test_collate_pads(self):
        tok = CharTok()
        batch = make_collate(tok.pad_token_id)([encode(tok, "a", "b", 10), encode(tok, "a", "bcd", 10)])
        self.assertEqual(batch["input_ids"].shape, (2, 5))
        self.assertEqual(batch["attention_mask"][0].tolist(), [1, 1, 1, 0, 0])
        self.assertEqual(batch["labels"][0].tolist(), [-100, 98, 0, -100, -100])

    def test_epoch_history(self):
        log = [{"loss": 3.0, "epoch": 0.5}, {"loss": 2.0, "epoch": 1.0}, {"eval_loss": 1.0, "epoch": 1.0},
               {"eval_loss": 0.5, "epoch": 2.0}]
        rows = epoch_history(log)
        self.assertEqual([r["epoch"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["train_loss"], 2.5)
        self.assertIsNone(rows[1]["train_loss"])


class PenaltyTest(unittest.TestCase):
    def test_only_answer_words_penalized(self):
        penalized = torch.tensor([True, True, True, False, True])     # token 3 stands in for an end word
        p = AnswerRepetitionPenalty(penalized, prompt_len=2, penalty=2.0)
        ids = torch.tensor([[4, 0, 1, 2, 3]])                          # prompt 4, 0; answer 1, 2, 3
        raw = torch.tensor([[1.0, 2.0, -2.0, 4.0, 8.0]])
        scores = p(ids, raw)
        self.assertEqual(scores.tolist(), [[1.0, 1.0, -4.0, 4.0, 8.0]])
        self.assertEqual(raw.tolist(), [[1.0, 2.0, -2.0, 4.0, 8.0]])  # unchanged: generate() keeps it as the logits


class StopTest(unittest.TestCase):
    def test_stops_after_fourth_line(self):
        tok, prompt = CharTok(), "P:\n\n"                             # line breaks in the prompt don't count
        answers = ["a\nb\nc\nd\n", "a\nb\nc\nd", "a\n\nb\nc\nd\n", "a\nb\nc\nd\0\0"]
        n = max(map(len, answers))
        ids = torch.tensor([tok.encode(prompt + a.ljust(n, "\0")) for a in answers])
        stop = FourLineStop(tok, len(prompt))
        for j in range(1, n + 1):                                      # one call per generated token, as in generate
            done = stop(ids[:, :len(prompt) + j], None)
        self.assertEqual(done.tolist(), [True, False, True, False])
        self.assertEqual(stop.length, {0: 8, 2: 9})                    # up to and including the fourth line break


class SplitTest(unittest.TestCase):
    """The data E trains on: each stage's pairs, and the splits (no validation topic in the quatrain training split,
    held-out-trait disses in the test split only)."""

    def test_pairs(self):
        cfg = load_config()
        for stage, splits in STAGE_FILES.items():
            for split, (key, name) in splits.items():
                rows = read_jsonl(project_path(cfg["paths"][key]) / name)
                pairs = load_split(stage, split, cfg)
                self.assertEqual(len(pairs), len(rows))
                for (prompt, completion), r in zip(pairs, rows):
                    self.assertEqual(decode_lines(completion), r["lines"])
                    tags = re.findall(r"^\[(\w[\w']*)\]", completion, re.M)
                    self.assertEqual(tags, [WORD_RE.findall(l)[-1] for l in r["lines"]], r["id"])
                    head = prompt.split("\n")
                    if stage == 1:
                        self.assertEqual(head[:2], ["Traits: none", "Intensity: none"])
                    else:
                        self.assertIn(head[1], ("Intensity: mild", "Intensity: harsh"))

    def test_quatrain_topics_disjoint(self):
        cfg = load_config()["paths"]
        train = {r["topic"] for r in read_jsonl(project_path(cfg["corpus_dir"]) / "quatrains_train.jsonl")}
        val = {r["topic"] for r in read_jsonl(project_path(cfg["corpus_dir"]) / "quatrains_val.jsonl")}
        self.assertFalse(train & val)

    def test_heldout_traits_in_test_only(self):
        cfg = load_config()["paths"]
        with open(project_path(cfg["traits"]), encoding="utf-8") as f:
            heldout = {t for t, info in json.load(f).items() if info["heldout"]}
        for split in ("train", "val"):
            rows = read_jsonl(project_path(cfg["diss_dir"]) / f"{split}.jsonl")
            self.assertFalse([r["id"] for r in rows if heldout & set(r["traits"])], split)
        test = read_jsonl(project_path(cfg["diss_dir"]) / "test.jsonl")
        self.assertTrue(any(heldout & set(r["traits"]) for r in test))


if __name__ == "__main__":
    unittest.main()
