"""System E unit tests, with no model download. Run from the project root:  python -m unittest generation.test_gpt2_lm -v"""
import json, unittest

from utils import load_config, project_path
from generation.gpt2_lm import encode, encode_all, epoch_history, make_collate


class CharTok:
    """Stands in for the GPT-2 tokenizer: one token per character."""
    eos_token_id, pad_token_id = 0, 0

    def encode(self, text, add_special_tokens=False):
        return [ord(c) for c in text]


def read_jsonl(rel):
    with open(project_path(rel), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


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


class SplitTest(unittest.TestCase):
    """The splits E trains on: no validation topic in the quatrain training split, and held-out-trait disses in the
    test split only."""

    def test_quatrain_topics_disjoint(self):
        cfg = load_config()["paths"]
        train = {r["topic"] for r in read_jsonl(f"{cfg['corpus_dir']}/quatrains_train.jsonl")}
        val = {r["topic"] for r in read_jsonl(f"{cfg['corpus_dir']}/quatrains_val.jsonl")}
        self.assertFalse(train & val)

    def test_heldout_traits_in_test_only(self):
        cfg = load_config()["paths"]
        with open(project_path(cfg["traits"]), encoding="utf-8") as f:
            traits = json.load(f)
        heldout = {t for t, info in traits.items() if info["heldout"]}
        for split in ("train", "val"):
            rows = read_jsonl(f"{cfg['diss_dir']}/{split}.jsonl")
            self.assertFalse([r["id"] for r in rows if heldout & set(r["traits"])], split)
        test = read_jsonl(f"{cfg['diss_dir']}/test.jsonl")
        self.assertTrue(any(heldout & set(r["traits"]) for r in test))


if __name__ == "__main__":
    unittest.main()
