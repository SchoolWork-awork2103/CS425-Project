"""Phase 2: rhyme planner. Picks the four end words of a roast from the traits, before generation.

For each trait, a meaning centre is built from GloVe vectors of the trait (double weight), its synonyms and the
content words of its flip angle (data/traits.json; an unseen trait uses just its own word). Words close to that
centre are anchors. Similarity is corrected for hubness: generic words (quite, though, know) sit close to every
centre, so each word's similarity to the average common word is subtracted (GENERALITY_WEIGHT). Each anchor
gets the best rhyming partner, from the anchors themselves or from words that end lines in the training poems
(so the generators have seen them there). A plan is two such pairs with different
rhyme sounds, scored by the summed similarity of its four words; with two or more traits the couplets come from
different traits. Within a pair the closer word goes last, so the punchline lands on the trait.

End words are kept short and common, like the ones the disses end on (mean 1.1 syllables, 1% with three or more;
median Zipf 4.75): long rare words (implemented/oriented) made the generators force them into lines that don't fit.
Pairs that rhyme only through a shared ending, with the same consonant before the rhyme (optimistic/pessimistic,
encouraging/discouraging), are left out too: they read as one word twice, not as a rhyme.

    planner = RhymePlanner()
    planner.plan(["confident"], k=3)  ->  [{"pairs": [(a1, a2), (b1, b2)], "end_words": [...], "score": ...}, ...]
"""
import json, re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pronouncing
from wordfreq import zipf_frequency

from utils import load_config, project_path
from .rhyme import in_cmudict, phones, rhyme_key, rhyme_keys, rhymes, same_sound, word_syllables

GENERIC_SEEDS = ["boring", "lazy", "clueless", "awkward", "annoying"]    # no traits, or none GloVe knows
GENERALITY_WEIGHT = 0.5    # 0 gives generic filler (tough/enough, might/quite); 1+ drifts to rare insults everywhere
COMMON_WORDS = 10_000      # "average common word" = mean of the most frequent GloVe words
MAX_SYLLABLES = 2          # the disses' end words: 99% have one or two; longer ones get forced into lines
# on top of the diss blocklist: mental-health words, since the disses avoid disability insults
AVOID = {"psychopath", "sociopath", "psycho", "neurotic", "schizophrenic", "bipolar", "autistic", "retarded",
         "insane", "lunatic", "deranged", "demented", "maniac", "manic", "suicidal", "anorexic", "crippled"}
STOP = {"all", "and", "the", "who", "their", "own", "too", "with", "for", "you", "your", "they", "them", "that",
        "this", "about", "very", "much", "more", "most", "also", "just", "really", "even", "ever", "never", "always",
        "thing", "things", "something", "everything", "anything", "someone", "everyone", "anyone", "one", "ones",
        "but", "not", "can", "could", "would", "should", "will", "what", "when", "where", "how", "why", "which",
        "there", "here", "then", "than", "into", "onto", "from", "over", "under", "out", "off", "way", "lot", "get",
        "got", "gets", "make", "makes", "made", "being", "been", "have", "has", "had", "are", "was", "were", "does",
        "did", "doing", "myself", "yourself", "himself", "herself", "itself", "themselves", "others", "other"}
WORD = re.compile(r"[a-z]+")


def shared_ending(a, b):
    """The rhyme carries the same consonant in front too (optimistic/pessimistic, encouraging/discouraging), so the
    pair sounds like one ending twice. Different consonants (time/climb) or none on one side (treats/eats) are fine."""
    for pa in phones(a):
        for pb in phones(b):
            if rhyme_key(pa) != rhyme_key(pb):
                continue
            n = len(pronouncing.rhyming_part(pa).split())
            sa, sb = pa.split(), pb.split()
            if len(sa) > n and len(sb) > n and sa[-n - 1] == sb[-n - 1]:
                return True
    return False


class RhymePlanner:
    def __init__(self, cfg=None, n_neighbours=1500, anchor_min_zipf=3.5, partner_min_count=2, pairs_per_trait=40):
        cfg = cfg or load_config()
        prefix = project_path(cfg["paths"]["glove"])
        if not Path(f"{prefix}.npy").exists():
            raise FileNotFoundError(f"{prefix}.npy missing: run python data/prepare_glove.py path/to/glove.6B.zip")
        E = np.load(f"{prefix}.npy").astype(np.float32)
        self.E = E / np.maximum(np.linalg.norm(E, axis=1, keepdims=True), 1e-8)
        common = self.E[:COMMON_WORDS].mean(0)
        self.generality = self.E @ (common / np.linalg.norm(common))
        self.vocab = Path(f"{prefix}.vocab.txt").read_text(encoding="utf-8").split("\n")[:len(E)]
        self.index = {w: i for i, w in enumerate(self.vocab)}
        self.traits = json.load(open(project_path(cfg["paths"]["traits"]), encoding="utf-8"))
        self.n_neighbours, self.anchor_min_zipf, self.pairs_per_trait = n_neighbours, anchor_min_zipf, pairs_per_trait
        blocklist = project_path(cfg["paths"]["blocklist"]).read_text(encoding="utf-8").splitlines()
        self.avoid = AVOID | {w.strip().lower() for w in blocklist if w.strip() and not w.startswith("#")}

        # partners: words that end lines in the training poems, grouped by rhyme sound
        ends = Counter()
        for path in (project_path(cfg["paths"]["corpus_dir"]) / "quatrains_train.jsonl",
                     project_path(cfg["paths"]["diss_dir"]) / "train.jsonl"):
            for line in open(path, encoding="utf-8"):
                r = json.loads(line)
                ends.update(w for p in r["rhymes"] for w in p)
        self.line_ends = {w for w, c in ends.items() if c >= partner_min_count and self.usable(w)}
        self.by_sound = defaultdict(set)
        for w in self.line_ends:
            for k in rhyme_keys(w):
                self.by_sound[k].add(w)

    def usable(self, w):
        return (w.isalpha() and len(w) >= 3 and w not in STOP and w not in self.avoid and w in self.index
                and in_cmudict(w) and word_syllables(w) <= MAX_SYLLABLES)

    def seeds(self, trait):
        """Weighted seed words for a trait: itself x2, its synonyms and the content words of its flip angle."""
        info = self.traits.get(trait, {})
        seeds = [(trait, 2.0)] if trait in self.index else []
        for phrase in [*info.get("synonyms", []), info.get("flip", "")]:
            for w in WORD.findall(phrase.lower()):
                if w in self.index and w not in STOP and len(w) >= 3:
                    seeds.append((w, 1.0))
        return seeds

    def centre(self, seeds):
        if not seeds:
            return None
        c = sum(wt * self.E[self.index[w]] for w, wt in seeds)
        return c / np.linalg.norm(c)

    def pairs(self, centre, exclude=()):
        """Best rhyme pairs near a meaning centre: [(score, (w1, w2))], closer word last."""
        sims = self.E @ centre - GENERALITY_WEIGHT * self.generality
        anchors =[self.vocab[i] for i in np.argsort(-sims)[:self.n_neighbours]]
        anchors = [w for w in anchors if self.usable(w) and w not in exclude
                   and zipf_frequency(w, "en") >= self.anchor_min_zipf]
        sound = defaultdict(set, {k: set(v) for k, v in self.by_sound.items()})
        for w in anchors:                                      # anchors can partner each other
            for k in rhyme_keys(w):
                sound[k].add(w)
        sim = lambda w: float(sims[self.index[w]])
        best = {}
        for a in anchors:
            partners = {p for k in rhyme_keys(a) for p in sound[k]
                        if p != a and p not in exclude and rhymes(a, p) and not shared_ending(a, p)}
            if not partners:
                continue
            p = max(partners, key=sim)
            pair = tuple(sorted((a, p), key=sim))
            best[frozenset(pair)] = (sim(a) + sim(p), pair)
        return sorted(best.values(), reverse=True)[:self.pairs_per_trait]

    def plan(self, traits, k=5, exclude=()):
        """Top k rhyme plans for the traits. exclude: words not to use (e.g. end words of recent replies)."""
        traits = [t.lower().strip() for t in traits if t.strip()]
        centres = [c for c in (self.centre(self.seeds(t)) for t in traits) if c is not None]
        if not centres:
            centres = [self.centre([(w, 1.0) for w in GENERIC_SEEDS])]
        lists = [self.pairs(c, set(exclude)) for c in centres]

        if len(lists) == 1:
            combos = [(a, b) for i, a in enumerate(lists[0]) for b in lists[0][i + 1:]]
        else:                                                  # each couplet from a different trait
            combos = [(a, b) for i, la in enumerate(lists) for j, lb in enumerate(lists) if i < j
                      for a in la for b in lb]
        plans, used = [], Counter()
        for (sa, pa), (sb, pb) in sorted(combos, key=lambda c: -(c[0][0] + c[1][0])):
            if set(pa) & set(pb) or same_sound(pa[0], pb[0]):
                continue
            if used[pa] >= 2 or used[pb] >= 2:                 # keep the top plans varied
                continue
            used[pa] += 1
            used[pb] += 1
            plans.append({"pairs": [pa, pb], "end_words": [*pa, *pb], "score": round(sa + sb, 4)})
            if len(plans) == k:
                break
        return plans


_default = None


def plan_rhymes(traits, k=5, exclude=()):
    """Module-level shortcut with a shared planner (GloVe is loaded once)."""
    global _default
    if _default is None:
        _default = RhymePlanner()
    return _default.plan(traits, k, exclude)
