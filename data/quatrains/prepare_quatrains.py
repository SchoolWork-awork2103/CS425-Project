"""Phase 1a, steps 6, 8 and 9: clean the generated quatrain corpus and split it by topic group.

Run from the project root:  python data/quatrains/prepare_quatrains.py
"""
import json, random, re, sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from nltk.stem import PorterStemmer
from nltk.tag.perceptron import PerceptronTagger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # data/: form_checks
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # project root: utils
from utils import load_config, normalize_text, project_path, set_seed
from form_checks import drop_reason, last_word

MAX_VAL_GROUP_FRAC = 0.25      # a topic group may fill at most this share of validation, so it spans many subjects
MIN_AFFIX_LEN = 4              # shortest noun that links by prefix/suffix (toast/toaster), so "car" doesn't match "cart"
SPELLING = {"wi-fi": "wifi", "neighbour": "neighbor"}
GENERIC_NOUNS = {"someone", "something", "thing", "things", "everyone", "everything", "nobody", "nothing",
                 "anything", "anyone", "way", "lot", "kind", "bit", "time", "day"}
TOKEN_RE = re.compile(r"[a-z]+")


def load_tagger():
    try:
        return PerceptronTagger()
    except LookupError:
        sys.exit("NLTK tagger missing: run  python -c \"import nltk; nltk.download('averaged_perceptron_tagger'); "
                 "nltk.download('averaged_perceptron_tagger_eng')\"")


def topic_nouns(topics):
    """The nouns of each topic. A word tagged as a noun in any topic counts as one in every topic, because the
    tagger is inconsistent on short phrases ("damp gym mat" vs "a gym membership")."""
    tagger, tokens = load_tagger(), {}
    for t in topics:
        text = t.lower()
        for a, b in SPELLING.items():
            text = text.replace(a, b)
        tokens[t] = TOKEN_RE.findall(text)
    nouns = {w for t in topics for w, tag in tagger.tag(tokens[t]) if tag.startswith("NN")} - GENERIC_NOUNS
    return {t: {w for w in tokens[t] if w in nouns and len(w) > 2} for t in topics}


def nouns_related(forms_a, forms_b):
    """Same noun after stemming, or one starts or ends with the other (toast/toaster, storm/rainstorm).
    Loose on purpose: a false link only keeps a topic out of validation, a missed one leaks a subject into train."""
    for x in forms_a:
        for y in forms_b:
            short, long = sorted((x, y), key=len)
            if short == long or (len(short) >= MIN_AFFIX_LEN and (long.startswith(short) or long.endswith(short))):
                return True
    return False


def topic_groups(nouns):
    """Connected groups of topics: two topics are linked when they have related nouns."""
    stemmer, topics = PorterStemmer(), sorted(nouns)
    vocab = sorted(set().union(*nouns.values()))
    forms = {w: {w, stemmer.stem(w), w[:-1] if w.endswith("s") else w} for w in vocab}

    parent = {x: x for x in [*topics, *(("noun", w) for w in vocab)]}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for t in topics:
        for w in nouns[t]:
            parent[find(t)] = find(("noun", w))
    for i, a in enumerate(vocab):
        for b in vocab[i + 1:]:
            if nouns_related(forms[a], forms[b]):
                parent[find(("noun", a))] = find(("noun", b))

    groups = defaultdict(list)
    for t in topics:
        groups[find(t)].append(t)
    return sorted(sorted(g) for g in groups.values())


def main():
    cfg = load_config()
    seed = set_seed(cfg["seed"])
    src = project_path(cfg["paths"]["quatrains"])
    out = project_path(cfg["paths"]["corpus_dir"])
    out.mkdir(parents=True, exist_ok=True)

    raw = [json.loads(l) for l in open(src, encoding="utf-8")]
    kept, dropped = [], Counter()
    for q in raw:
        why = drop_reason(q["lines"])
        lines = [normalize_text(l) for l in q["lines"]]
        rhymes = [[w.lower() for w in p] for p in q["rhymes"]]
        if not why and [last_word(l) for l in lines] != [w for p in rhymes for w in p]:
            why = "end_word_mismatch"
        if why:
            dropped[why] += 1
            continue
        kept.append({"id": q["id"], "topic": q["topic"], "tone": q["tone"], "voice": q["voice"],
                     "lines": lines, "rhymes": rhymes, "syllables": q["syllables"], "score": q["score"]})

    # 95/5 split by topic group: whole groups go to validation until it holds the target share, so no
    # validation topic shares a noun with a training topic. Groups too big for validation stay in train, and so
    # do topics with no noun at all, since there is nothing to check them against.
    by_topic = Counter(q["topic"] for q in kept)
    nouns = topic_nouns(sorted(by_topic))
    groups = topic_groups(nouns)
    size = lambda g: sum(by_topic[t] for t in g)
    target = cfg["data"]["quatrain_val_frac"] * len(kept)
    candidates = [g for g in groups if size(g) <= MAX_VAL_GROUP_FRAC * target and all(nouns[t] for t in g)]
    random.Random(seed).shuffle(candidates)
    val_groups, val_topics, n_val = [], set(), 0
    for g in candidates:
        if n_val >= target:
            break
        val_groups.append(g)
        val_topics.update(g)
        n_val += size(g)
    largest = max(groups, key=size)
    train = [q for q in kept if q["topic"] not in val_topics]
    val = [q for q in kept if q["topic"] in val_topics]

    for name, rows in (("quatrains_train.jsonl", train), ("quatrains_val.jsonl", val)):
        with open(out / name, "w", encoding="utf-8") as f:
            f.writelines(json.dumps(q, ensure_ascii=False) + "\n" for q in rows)

    meta = {
        "date": date.today().isoformat(),
        "source": cfg["paths"]["quatrains"],
        "raw": len(raw),
        "dropped": dict(dropped),
        "kept": len(kept),
        "normalization": "lowercase; curly quotes -> straight; em/en dash -> ' - '; ellipsis -> '...'; "
                         "asterisks removed; accents folded to ASCII; whitespace collapsed",
        "split": {"by": "topic group: topics linked by a shared noun (POS-tagged, Porter-stemmed, or one noun "
                        f"starting or ending with the other, at least {MIN_AFFIX_LEN} letters); "
                        "topics with no noun stay in train",
                  "seed": seed, "train": len(train), "val": len(val),
                  "train_topics": len(by_topic) - len(val_topics), "val_topics": len(val_topics),
                  "groups": len(groups), "largest_group": {"topics": len(largest), "quatrains": size(largest)},
                  "max_val_group": int(MAX_VAL_GROUP_FRAC * target), "val_groups": len(val_groups),
                  "no_noun_topics": sum(not n for n in nouns.values())},
        "val_groups": sorted(val_groups),
    }
    json.dump(meta, open(out / "prep_meta.json", "w", encoding="utf-8"), indent=2)

    print(f"raw {len(raw)} -> kept {len(kept)}  dropped {dict(dropped)}")
    print(f"{len(groups)} topic groups, largest {len(largest)} topics / {size(largest)} quatrains (train only)")
    print(f"train {len(train)} ({meta['split']['train_topics']} topics) | "
          f"val {len(val)} ({len(val_topics)} topics in {len(val_groups)} groups)")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
