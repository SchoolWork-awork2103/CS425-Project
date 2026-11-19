"""Phase 2: form scores for a quatrain, each in [0, 1]. Used by the reranker and the automatic evaluation."""
from .rhyme import in_cmudict, last_word, line_syllables, near_rhyme, rhymes, same_sound, words_of

SAME_SOUND_PENALTY = 0.25           # A and B couplets on the same rhyme sound read as AAAA
# syllable limits follow the diss data (diss_form in config.yaml: median 14 syllables), not the older 7-11 guess
SYL_MIN, SYL_MAX, PAIR_DIFF = 6, 18, 5


def couplet_score(a, b):
    return 1.0 if rhymes(a, b) else 0.5 if near_rhyme(a, b) else 0.0


def aabb_score(lines):
    """Mean of the two couplets (1 exact rhyme, 0.5 near rhyme, 0 none), minus a penalty when the A and B rhyme
    sounds are the same. Anything that is not four lines scores 0."""
    if len(lines) != 4:
        return 0.0
    e = [last_word(l) for l in lines]
    score = (couplet_score(e[0], e[1]) + couplet_score(e[2], e[3])) / 2
    if same_sound(e[0], e[2]):
        score -= SAME_SOUND_PENALTY
    return max(score, 0.0)


def syllable_score(lines, syl_min=SYL_MIN, syl_max=SYL_MAX, pair_diff=PAIR_DIFF):
    """Half for the share of lines within the syllable range, half for the share of couplets whose two lines are
    within pair_diff syllables of each other. There is no fixed metre, only balance."""
    if len(lines) != 4:
        return 0.0
    syl = [line_syllables(l) for l in lines]
    in_range = sum(syl_min <= s <= syl_max for s in syl) / 4
    balanced = sum(abs(syl[i] - syl[i + 1]) <= pair_diff for i in (0, 2)) / 2
    return (in_range + balanced) / 2


def lexical_score(lines, vocab=None):
    """Share of words that are real: in CMUdict, or in vocab (e.g. the GloVe vocabulary) when given."""
    if isinstance(lines, str):
        lines = [lines]
    ws = [w for l in lines for w in words_of(l)]
    if not ws:
        return 0.0
    return sum(in_cmudict(w) or (vocab is not None and w in vocab) for w in ws) / len(ws)


def form_scores(lines, vocab=None):
    return {"aabb": aabb_score(lines), "syllables": syllable_score(lines), "lexical": lexical_score(lines, vocab)}
