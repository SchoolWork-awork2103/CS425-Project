"""AABB form checks from quatrain_gen.ipynb, so the diss data is checked with the same rules as the quatrain
corpus. Changed for the disses: rhymes ignore primary vs secondary stress (elevate/fate), and leftover [tags]
and end words stapled onto a line are rejected. Phase 2 grows this into the phonetics/ module.
"""
import re, unicodedata
from collections import Counter

import pronouncing
from wordfreq import zipf_frequency

SYL_MIN, SYL_MAX = 6, 12    # allowed syllables per line
PAIR_SYL_DIFF    = 3        # max syllable difference within a couplet
MAX_OOV_RATE     = 0.15     # max share of words not in CMUdict
MIN_END_ZIPF     = 2.5      # end words must be at least this common (wordfreq Zipf scale)
NEAR_DUP_ROUGE   = 0.7      # ROUGE-L F1 above this = near-duplicate

WORD_RE   = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
QUOTE_MAP = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})
TAIL_RE   = re.compile(r"([A-Za-z']+)\s*,\s*([A-Za-z']+)[\s.,!?;:]*$")
SYMBOL_RE = re.compile(r"[0-9$%@&+_/#=<>]")


def normalize(text):
    return text.translate(QUOTE_MAP)        # curly quotes -> straight, so "I’ll" stays one word


def words_of(line):
    return [w.lower() for w in WORD_RE.findall(normalize(line))]


def last_word(line):
    w = words_of(line)
    return w[-1] if w else ""


def drop_reason(lines):
    """Why raw generated lines can't be used, or None. Checked before normalizing."""
    for l in lines:
        if "[" in l or "]" in l:
            return "leftover_tag"        # a [word] tag at the end of a line was read as the end word
        if any(ch.isalpha() and not ch.isascii() and "LATIN" not in unicodedata.name(ch, "") for ch in l):
            return "non_latin"
        if SYMBOL_RE.search(l):
            return "digits_symbols"      # digits are not counted as syllables and tokenize badly
    return None


def all_phones(word):
    return pronouncing.phones_for_word(word.lower())


def rhyme_key(phones):
    # rhyming part with stress levels dropped, so a secondary stress rhymes with a primary one
    # (elevate/fate, doormat/chat, approach/cockroach)
    return re.sub(r"\d", "", pronouncing.rhyming_part(phones))


def rhyme_parts(word):
    return {rhyme_key(p) for p in all_phones(word)}


def same_sound(a, b):
    # True if a and b share a rhyme sound (identical words count)
    ra, rb = rhyme_parts(a), rhyme_parts(b)
    return bool(ra and rb and ra & rb)


def identical_rhyme(pa, pb):
    # Not a real rhyme if one pronunciation is the other plus extra syllables in front
    # (play/replay, side/inside, way/away) or they sound the same (one/won).
    # Extra consonants are fine: air/chair, red/spread, in/grin.
    a, b = pa.split(), pb.split()
    short, long_ = sorted((a, b), key=len)
    unstressed = lambda ps: [re.sub(r"\d", "", p) for p in ps]     # as in rhyme_key
    if unstressed(long_[-len(short):]) != unstressed(short):
        return False
    extra = long_[:len(long_) - len(short)]
    return not extra or any(p[-1].isdigit() for p in extra)


def rhymes(a, b):
    a, b = a.lower(), b.lower()
    if not a or not b or a == b:
        return False
    return any(rhyme_key(pa) == rhyme_key(pb) and not identical_rhyme(pa, pb)
               for pa in all_phones(a) for pb in all_phones(b))


def word_syllables(word):
    ph = all_phones(word)
    if ph:
        return pronouncing.syllable_count(ph[0])
    groups = re.findall(r"[aeiouy]+", word.lower())       # fallback for unknown words
    n = len(groups)
    if word.lower().endswith("e") and n > 1 and not word.lower().endswith("le"):
        n -= 1
    return max(n, 1)


def line_syllables(line):
    return sum(word_syllables(w) for w in words_of(line))


def oov_rate(lines):
    ws = [w for l in lines for w in words_of(l)]
    return sum(1 for w in ws if not all_phones(w)) / len(ws) if ws else 1.0


def stapled(line):
    # "hit the floor, roar," / "the wave, brave,": a lone end word tacked on after a comma to force the rhyme.
    # Caught when it repeats an earlier word or shares the rhyme sound of the word before the comma.
    m = TAIL_RE.search(normalize(line))
    if not m:
        return False
    before, last = m.group(1).lower(), m.group(2).lower()
    return last in words_of(line)[:-1] or same_sound(before, last)


def check(lines, syl_min=SYL_MIN, syl_max=SYL_MAX, pair_diff=PAIR_SYL_DIFF):
    # the syllable limits default to the quatrain corpus; the disses pass looser ones
    r = {"lines": lines, "ends": None, "syllables": None, "oov": None, "reasons": []}
    if len(lines) != 4:
        r["reasons"].append(f"line_count={len(lines)}")
    else:
        if any("[" in l or "]" in l for l in lines):
            r["reasons"].append("leftover_tag")   # a tag left in the line would be read as the end word
        if any(stapled(l) for l in lines):
            r["reasons"].append("stapled_end_word")
        ends = [last_word(l) for l in lines]
        r["ends"] = ends
        a_ok, b_ok = rhymes(ends[0], ends[1]), rhymes(ends[2], ends[3])
        if not a_ok and not b_ok and same_sound(ends[0], ends[2]) and same_sound(ends[1], ends[3]):
            r["reasons"].append("ABAB")
        else:
            if not a_ok: r["reasons"].append("A_no_rhyme")
            if not b_ok: r["reasons"].append("B_no_rhyme")
            if a_ok and b_ok and same_sound(ends[0], ends[2]): r["reasons"].append("same_sound_AB")
        syl = [line_syllables(l) for l in lines]
        r["syllables"] = syl
        if any(s < syl_min or s > syl_max for s in syl):
            r["reasons"].append("syllable_range")
        if abs(syl[0] - syl[1]) > pair_diff or abs(syl[2] - syl[3]) > pair_diff:
            r["reasons"].append("pair_unbalanced")
        if any(zipf_frequency(e, "en") < MIN_END_ZIPF for e in ends):
            r["reasons"].append("rare_end_word")
        r["oov"] = round(oov_rate(lines), 3)
        if r["oov"] > MAX_OOV_RATE:
            r["reasons"].append("oov")
    r["pass"] = not r["reasons"]
    return r


def near_dup(a, ca, b, cb, threshold=NEAR_DUP_ROUGE):
    # ROUGE-L F1 > threshold? Word overlap is an upper bound on the LCS, so most pairs skip the DP.
    f1 = lambda n: 0.0 if n == 0 else 2 * n / (len(a) + len(b))
    if f1(sum((ca & cb).values())) <= threshold:
        return False
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return f1(prev[-1]) > threshold


if __name__ == "__main__":
    for a, b in [("late", "wait"), ("phone", "alone"), ("air", "chair"), ("one", "done"), ("in", "grin"),
                 ("red", "spread"), ("trace", "grace"), ("up", "cup")]:
        assert rhymes(a, b), (a, b)
    for a, b in [("elevate", "fate"), ("doormat", "chat"), ("approach", "cockroach"), ("deadline", "design")]:
        assert rhymes(a, b), (a, b)
    for a, b in [("late", "phone"), ("play", "replay"), ("side", "inside"), ("way", "away"), ("one", "won"),
                 ("happy", "me"), ("water", "later")]:
        assert not rhymes(a, b), (a, b)
    assert words_of("I’ll go") == ["i'll", "go"]
    for l in ["You roar out loud but trip and hit the floor, roar,", "you skipped the wave, brave,",
              "You strike a pose like it's your full compose, pose,", "You plant your flag, a half-wracked rag, flag,"]:
        assert stapled(l), l
    for l in ["and you know it, too.", "you lose every time, my friend.", "the crowd went wild, then quiet."]:
        assert not stapled(l), l
    print("form checks ok")
