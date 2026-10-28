"""Phase 2: rhymes and syllables from CMUdict (via `pronouncing`).

The rules are the ones the quatrain corpus and the disses were filtered with (data/form_checks.py), so generation,
reranking and evaluation judge rhyme exactly like the training data did:
  - two words rhyme when their rhyming parts (last stressed vowel onwards) match, ignoring stress level
    (elevate/fate), and neither is the other plus extra unstressed syllables in front (play/replay, way/away)
    or a homophone (one/won)
  - words missing from CMUdict never rhyme; their syllables are estimated from vowel groups
"""
import re
from functools import lru_cache

import pronouncing

WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


def words_of(line):
    return WORD_RE.findall(line.lower().replace("’", "'"))


def last_word(line):
    w = words_of(line)
    return w[-1] if w else ""


@lru_cache(maxsize=None)
def phones(word):
    return tuple(pronouncing.phones_for_word(word.lower()))


def in_cmudict(word):
    return bool(phones(word))


def rhyme_key(p):
    """Rhyming part of one pronunciation with stress levels dropped."""
    return re.sub(r"\d", "", pronouncing.rhyming_part(p))


@lru_cache(maxsize=None)
def rhyme_keys(word):
    return frozenset(rhyme_key(p) for p in phones(word))


def identical_rhyme(pa, pb):
    """One pronunciation is the other plus extra unstressed syllables in front (play/replay, side/inside), or they
    sound the same (one/won). Extra consonants are fine: air/chair, red/spread, in/grin."""
    a, b = pa.split(), pb.split()
    short, long_ = sorted((a, b), key=len)
    unstressed = lambda ps: [re.sub(r"\d", "", p) for p in ps]
    if unstressed(long_[-len(short):]) != unstressed(short):
        return False
    extra = long_[:len(long_) - len(short)]
    return not extra or any(p[-1].isdigit() for p in extra)


@lru_cache(maxsize=None)
def rhymes(a, b):
    a, b = a.lower(), b.lower()
    if not a or not b or a == b:
        return False
    return any(rhyme_key(pa) == rhyme_key(pb) and not identical_rhyme(pa, pb)
               for pa in phones(a) for pb in phones(b))


@lru_cache(maxsize=None)
def near_rhyme(a, b):
    """Not a full rhyme, but the same stressed vowel in the rhyming part (time/mine, home/alone)."""
    a, b = a.lower(), b.lower()
    if not a or not b or a == b or rhymes(a, b):
        return False
    vowel = lambda p: re.sub(r"\d", "", pronouncing.rhyming_part(p).split()[0])
    return any(vowel(pa) == vowel(pb) and not identical_rhyme(pa, pb) for pa in phones(a) for pb in phones(b))


def same_sound(a, b):
    """a and b share a rhyme sound (identical words count); used to keep the A and B couplets apart."""
    ka, kb = rhyme_keys(a), rhyme_keys(b)
    return bool(ka and kb and ka & kb)


@lru_cache(maxsize=None)
def word_syllables(word):
    ph = phones(word)
    if ph:
        return pronouncing.syllable_count(ph[0])
    w = word.lower()
    n = len(re.findall(r"[aeiouy]+", w))                  # fallback for unknown words
    if w.endswith("e") and n > 1 and not w.endswith("le"):
        n -= 1
    return max(n, 1)


def line_syllables(line):
    return sum(word_syllables(w) for w in words_of(line))
