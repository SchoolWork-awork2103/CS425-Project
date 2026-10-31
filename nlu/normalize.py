"""Phase 6: map a TRAIT span found by the NLU model to a trait key in data/traits.json.

Tried in order, on the span:
  key      a trait key in it, or another form of one (loyalty -> loyal, patience -> patient, creativity -> creative)
  synonym  a synonym phrase from traits.json ("tells it like it is" -> honest), the longest match first
  nearest  sentence embeddings (all-MiniLM-L6-v2): the span's 7 nearest labelled spans from the NLU training split
           vote with their similarity, and every trait adds its similarity to its description ("confident:
           self-assured, bold, ..."). Traits with no training spans (the held-out ones) get the full description
           weight, the others DESC_WEIGHT_SEEN of it, since their spans already speak for them.
If the span is no closer than the threshold (config.yaml, nlu.unknown_threshold) to any training span or description,
it is unknown: trait None, with the nearest trait kept for the dialogue manager ("use the nearest trait and say so").

Why not GloVe as first planned: most spans describe the trait indirectly ("set financial goals for everything"), and
the mean GloVe vector of their words picked the labelled trait for only 20-33% of the gold spans, against 39-57% here.

    norm = TraitNormalizer()
    norm("set financial goals for everything")  ->  {"trait": "frugal", "how": "nearest", "score": 0.52}
"""
import json, os, re

import numpy as np

from utils import load_config, project_path

WORD = re.compile(r"[a-z]+")
STOP = {"a", "an", "the", "and", "or", "but", "so", "to", "of", "in", "on", "at", "by", "for", "with", "about", "as",
        "is", "am", "are", "was", "be", "been", "it", "its", "this", "that", "i", "me", "my", "im", "you", "your",
        "we", "they", "them", "their", "he", "she", "his", "her", "who", "what", "do", "does", "did", "don", "t",
        "s", "m", "ve", "ll", "d", "re", "too", "very", "really", "just", "like", "all", "people", "say", "call"}
K = 7
DESC_WEIGHT_SEEN = 0.3


def spans_of(tokens, tags):
    """BIO tags -> the tagged spans as token lists. An I-TRAIT with no B-TRAIT before it starts a span."""
    spans, cur = [], None
    for tok, tag in zip(tokens, tags):
        if tag == "B-TRAIT" or (tag == "I-TRAIT" and cur is None):
            cur = [tok]
            spans.append(cur)
        elif tag == "I-TRAIT":
            cur.append(tok)
        else:
            cur = None
    return spans


def other_form(word, key):
    """True if word looks like another form of the trait key: a shared stem of at least 5 letters that covers most of
    both words (loyalty/loyal, patience/patient, adventure/adventurous), but not general/generous or create/creature."""
    n = len(os.path.commonprefix([word, key]))
    return n >= 5 and n >= len(key) - 3 and n >= 0.7 * len(word)


class TraitNormalizer:
    def __init__(self, cfg=None, threshold=None, encoder=None):
        from sentence_transformers import SentenceTransformer
        cfg = cfg or load_config()
        self.traits = json.load(open(project_path(cfg["paths"]["traits"]), encoding="utf-8"))
        self.threshold = cfg["nlu"]["unknown_threshold"] if threshold is None else threshold
        self.synonyms = sorted(((" ".join(WORD.findall(s.lower())), t) for t, v in self.traits.items()
                                for s in v["synonyms"]), key=lambda x: -len(x[0]))
        self.encoder = encoder or SentenceTransformer(cfg["nlu"]["span_encoder"])
        self.names = list(self.traits)
        self.desc_vecs = self.embed([f"{t}: {', '.join(v['synonyms'])}" for t, v in self.traits.items()])
        # labelled spans from the NLU training split only, so val and test spans are never looked up
        spans, labels = [], []
        for line in open(project_path(cfg["paths"]["nlu_dir"]) / "train.jsonl", encoding="utf-8"):
            r = json.loads(line)
            found = spans_of(r["tokens"], r["tags"])
            if len(found) == len(r["traits"]):
                spans += [" ".join(s) for s in found]
                labels += r["traits"]
        self.span_vecs, self.span_traits = self.embed(spans), labels
        seen = set(labels)
        self.desc_weight = np.array([DESC_WEIGHT_SEEN if t in seen else 1.0 for t in self.names])

    def embed(self, texts):
        return self.encoder.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)

    def rule(self, span):
        text = " ".join(WORD.findall(span.lower().replace("’", "'")))
        for w in text.split():
            if w not in STOP:
                for t in self.names:
                    if w == t or other_form(w, t):
                        return {"trait": t, "how": "key", "score": 1.0}
        for s, t in self.synonyms:
            if re.search(rf"\b{re.escape(s)}\b", text):
                return {"trait": t, "how": "synonym", "score": 1.0}
        return None

    def nearest(self, vecs):
        out = []
        for v in vecs:
            sims = self.span_vecs @ v
            top = np.argsort(-sims)[:K]
            desc = self.desc_vecs @ v
            score = K * desc * self.desc_weight
            for j in top:
                score[self.names.index(self.span_traits[j])] += sims[j]
            best = self.names[int(score.argmax())]
            closeness = float(max(sims[top[0]], desc.max()))
            if closeness >= self.threshold:
                out.append({"trait": best, "how": "nearest", "score": round(closeness, 3)})
            else:
                out.append({"trait": None, "how": "unknown", "score": round(closeness, 3), "nearest": best})
        return out

    def many(self, spans):
        out = [self.rule(s) for s in spans]
        todo = [i for i, r in enumerate(out) if r is None]
        if todo:
            for i, r in zip(todo, self.nearest(self.embed([spans[i] for i in todo]))):
                out[i] = r
        return out

    def __call__(self, span):
        return self.many([span])[0]
