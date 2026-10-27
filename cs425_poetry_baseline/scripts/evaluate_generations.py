"""Check format/AABB phonetics for generated 4-line poems; not a humour evaluator."""
import argparse
from collections import Counter
import json
from pathlib import Path
from prepare_data import aabb_status


def evaluate(input_path):
    stats = Counter()
    for line in input_path.open(encoding='utf-8'):
        if not line.strip():
            continue
        row = json.loads(line)
        lines = [x.strip() for x in row['poem'].splitlines() if x.strip()]
        stats['samples'] += 1
        if len(lines) != 4:
            stats['not_four_lines'] += 1
            continue
        stats['four_lines'] += 1
        stats['aabb_' + aabb_status(lines)] += 1
    n = stats['samples']
    stats['four_line_rate'] = round(stats['four_lines']/n, 4) if n else None
    stats['strict_aabb_rate'] = round(stats['aabb_valid']/n, 4) if n else None
    return dict(stats)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(evaluate(args.input), indent=2))
