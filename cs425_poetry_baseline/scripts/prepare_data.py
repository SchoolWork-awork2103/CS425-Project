"""Audit 4-line poems and make reproducible, topic-disjoint splits (stdlib + cmudict)."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import re

import cmudict

WORD = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?")
LEXICON = cmudict.dict()


def last_word(line):
    words = WORD.findall(line)
    return words[-1].lower().replace('’', "'") if words else ''


def rhyme_tail(pronunciation):
    # Extract from the last stressed vowel; fall back to any final vowel.
    i = next((i for i in range(len(pronunciation)-1, -1, -1)
              if pronunciation[i].endswith(('1', '2'))), None)
    if i is None:
        i = next((i for i in range(len(pronunciation)-1, -1, -1)
                  if pronunciation[i][-1:].isdigit()), None)
    if i is None:
        return None
    return tuple(re.sub(r'[012]', '', p) for p in pronunciation[i:])


def rhyme_tails(word):
    return {tail for pron in LEXICON.get(word, [])
            if (tail := rhyme_tail(pron)) is not None}


def aabb_status(lines):
    """Return 'valid', 'invalid', or 'unknown' if a word is absent from CMUdict."""
    if len(lines) != 4 or any(not isinstance(line, str) for line in lines):
        return 'invalid'
    endings = [last_word(s) for s in lines]
    if len(set(endings)) != 4:
        return 'invalid'
    tails = [rhyme_tails(w) for w in endings]
    if not all(tails):
        return 'unknown'
    a = tails[0] & tails[1]
    b = tails[2] & tails[3]
    return 'valid' if a and b and a.isdisjoint(b) else 'invalid'


def prepare(source, out_dir, seed):
    records = []
    format_errors = 0
    rhyme_stats = Counter()
    ratings = Counter()
    voices = Counter()
    tones = Counter()
    seen_poems = set()
    duplicates = 0
    annotated_endings_mismatch = 0
    for line_no, line in enumerate(source.open(encoding='utf-8'), 1):
        try:
            row = json.loads(line)
            lines = row['lines']
            topic, tone, voice = (row[k] for k in ('topic', 'tone', 'voice'))
            if (not isinstance(lines, list) or len(lines) != 4 or
                any(not isinstance(s, str) or not s.strip() for s in lines) or
                any(not isinstance(v, str) or not v.strip() for v in (topic, tone, voice))):
                format_errors += 1
                continue
        except (KeyError, ValueError, TypeError):
            format_errors += 1
            continue
        poem = '\n'.join(s.strip() for s in lines)
        if poem in seen_poems:
            duplicates += 1
            continue
        seen_poems.add(poem)
        status = aabb_status(lines)
        rhyme_stats[status] += 1
        # Annotation is metadata from the data generator, NOT independent proof of rhyme.
        annotations = row.get('rhymes', [])
        endings = [last_word(s) for s in lines]
        if (len(annotations) != 2 or any(
            not isinstance(pair, list) or len(pair) != 2 or
            [str(x).lower() for x in pair] != endings[2*i:2*i+2]
            for i, pair in enumerate(annotations)
        )):
            annotated_endings_mismatch += 1
        ratings[str(row.get('score', 'missing'))] += 1
        voices[voice] += 1
        tones[tone] += 1
        prompt = (f'Topic: {topic}\nTone: {tone}\nVoice: {voice}\n'
                  'Write a four-line poem with an AABB rhyme scheme.\nPoem:\n')
        records.append({'id': row.get('id', line_no), 'topic': topic,
                        'tone': tone, 'voice': voice, 'score': row.get('score'),
                        'prompt': prompt, 'completion': poem, 'aabb_status': status})

    # Split by TOPIC rather than random poem: identical topics never cross train/val/test.
    by_topic = defaultdict(list)
    for row in records:
        by_topic[row['topic']].append(row)
    rng = random.Random(seed)
    topics = sorted(by_topic)
    rng.shuffle(topics)
    splits = {'train': [], 'validation': [], 'test': []}
    thresholds = {'train': int(0.8 * len(records)), 'validation': int(0.1 * len(records))}
    stage = 'train'
    for topic in topics:
        if stage == 'train' and len(splits['train']) >= thresholds['train']:
            stage = 'validation'
        if stage == 'validation' and len(splits['validation']) >= thresholds['validation']:
            stage = 'test'
        splits[stage].extend(by_topic[topic])
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in splits.items():
        rng.shuffle(data)
        with (out_dir / f'{name}.jsonl').open('w', encoding='utf-8') as f:
            for row in data:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
    summary = {
        'source': source.name,
        'parsed_valid_unique_poems': len(records),
        'invalid_structure_or_json': format_errors,
        'exact_duplicate_poems_removed': duplicates,
        'aabb_check_cmudict': dict(rhyme_stats),
        'rhyme_annotation_end_word_mismatches': annotated_endings_mismatch,
        'unique_topics': len(by_topic),
        'tones': dict(tones.most_common()),
        'voices': dict(voices.most_common()),
        'scores': dict(ratings.most_common()),
        'split_strategy': 'topic-disjoint 80/10/10 approx; seed '+str(seed),
        'splits': {name: {'poems': len(data), 'topics': len(set(x['topic'] for x in data))}
                   for name, data in splits.items()},
        'important_limitations': [
            'These are mostly general poetry topics, NOT labelled personalised diss examples.',
            'CMUdict validates known final-word pronunciations, not semantic quality or meter.',
            'Human review and a separate trait-to-diss dataset are still needed.'
        ],
    }
    (out_dir / 'audit_report.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('data'))
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    prepare(args.input, args.out, args.seed)
