"""Fast tests for the deterministic dataset and rhyme helper. No model downloads."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from prepare_data import aabb_status, last_word
from evaluate_generations import evaluate


class DataChecks(unittest.TestCase):
    def test_known_aabb(self):
        self.assertEqual(aabb_status([
            'You think you are so very bright',
            'Yet copy answers every night',
            'You promised work would be your art',
            'Then missed the deadline at the start',
        ]), 'valid')

    def test_aaaa_is_not_aabb(self):
        self.assertEqual(aabb_status([
            'Your homework waits all through the night',
            'You claim you are a shining light',
            'You keep on playing till first light',
            'You say tomorrow will be right',
        ]), 'invalid')

    def test_end_words(self):
        self.assertEqual(last_word('My day is bright!'), 'bright')

    def test_split_leakage(self):
        data_dir = Path(__file__).resolve().parents[1] / 'data'
        if not (data_dir / 'train.jsonl').exists():
            self.skipTest('No prepared data in sibling data/ directory')
        sets = {}
        for split in ('train', 'validation', 'test'):
            with (data_dir / f'{split}.jsonl').open() as f:
                sets[split] = {json.loads(line)['topic'] for line in f}
        self.assertFalse(sets['train'] & sets['validation'])
        self.assertFalse(sets['train'] & sets['test'])
        self.assertFalse(sets['validation'] & sets['test'])


if __name__ == '__main__':
    unittest.main()
