"""Phase 6: joint intent + TRAIT slot model. DistilBERT with an intent head on [CLS] and a BIO tag head on the tokens.

The data (data/nlu/prepare_nlu.py) is tagged on whitespace tokens. Each word's tag goes on its first word piece and
the other pieces are left out of the loss (-100); at prediction a word takes the tag of its first piece. The loss is
the sum of the intent and the tag cross-entropy. Slot F1 counts a predicted span as right only if it covers exactly
the words of a gold span.

Training and evaluation: python nlu/train_nlu.py. The dialogue manager loads the trained model with

    nlu = NLU.load("checkpoints/nlu_joint_best")
    nlu.parse("roast me, i set financial goals for everything")
    -> {"intent": "request_diss", "confidence": 0.99,
        "traits": [{"span": "set financial goals for everything", "trait": "frugal", "how": "nearest", ...}]}
"""
import json, re, time
from pathlib import Path

import torch
from torch import nn
from transformers import AutoConfig, AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

INTENTS = ["request_diss", "another_one", "make_meaner", "make_softer", "greet", "goodbye", "out_of_scope"]
TAGS = ["O", "B-TRAIT", "I-TRAIT"]
TOKEN_RE = re.compile(r"\S+")      # the same split as prepare_nlu.py
EDGE_PUNCT = ".,!?;:\"'()[]*…“”‘’"
MERGE_GAP = 1                      # predicted spans at most this many words apart are joined in NLU.parse


class JointModel(nn.Module):
    def __init__(self, encoder, dropout=0.1):
        super().__init__()
        self.encoder = encoder
        dim = encoder.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.intent_head = nn.Linear(dim, len(INTENTS))
        self.tag_head = nn.Linear(dim, len(TAGS))

    def forward(self, input_ids, attention_mask):
        h = self.dropout(self.encoder(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state)
        return self.intent_head(h[:, 0]), self.tag_head(h)


def encode(tok, tokens, tags=None, max_len=160):
    """Word pieces of a tokenized message, the tag label of each piece (-100 except on first pieces) and, for each
    word that survived truncation, the index of its first piece."""
    enc = tok(tokens, is_split_into_words=True, truncation=True, max_length=max_len)
    firsts, prev = {}, None
    for i, w in enumerate(enc.word_ids()):
        if w is not None and w != prev:
            firsts[w] = i
        prev = w
    labels = [-100] * len(enc.input_ids)
    if tags is not None:
        for w, i in firsts.items():
            labels[i] = TAGS.index(tags[w])
    return enc.input_ids, labels, firsts


def example(tok, row, max_len=160):
    ids, labels, _ = encode(tok, row["tokens"], row["tags"], max_len)
    return {"ids": ids, "labels": labels, "intent": INTENTS.index(row["intent"])}


def make_collate(pad_id):
    def collate(batch):
        n = max(len(b["ids"]) for b in batch)
        ids = torch.full((len(batch), n), pad_id)
        labels = torch.full((len(batch), n), -100)
        mask = torch.zeros((len(batch), n), dtype=torch.long)
        for i, b in enumerate(batch):
            ids[i, :len(b["ids"])] = torch.tensor(b["ids"])
            labels[i, :len(b["labels"])] = torch.tensor(b["labels"])
            mask[i, :len(b["ids"])] = 1
        return {"input_ids": ids, "attention_mask": mask, "labels": labels,
                "intent": torch.tensor([b["intent"] for b in batch])}
    return collate


def build(model_name, dropout=0.1):
    return JointModel(AutoModel.from_pretrained(model_name), dropout), AutoTokenizer.from_pretrained(model_name)


def save(model, tok, out_dir, extra=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.encoder.config.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    torch.save(model.state_dict(), out_dir / "model.pt")
    json.dump({"intents": INTENTS, "tags": TAGS, **(extra or {})}, open(out_dir / "labels.json", "w"), indent=2)


def load(path, device="cpu"):
    path = Path(path)
    model = JointModel(AutoModel.from_config(AutoConfig.from_pretrained(path)))
    model.load_state_dict(torch.load(path / "model.pt", map_location=device))
    return model.to(device).eval(), AutoTokenizer.from_pretrained(path)


@torch.no_grad()
def predict(model, tok, token_lists, device, batch_size=64, max_len=160):
    """Intent probabilities and per-word tags for whitespace-tokenized messages. Words cut off by truncation get O."""
    model.eval()
    out = []
    for s in range(0, len(token_lists), batch_size):
        chunk = token_lists[s:s + batch_size]
        encs = [encode(tok, t, max_len=max_len) for t in chunk]
        batch = make_collate(tok.pad_token_id)([{"ids": e[0], "labels": e[1], "intent": 0} for e in encs])
        intent_logits, tag_logits = model(batch["input_ids"].to(device), batch["attention_mask"].to(device))
        probs = intent_logits.softmax(-1).cpu()
        tag_ids = tag_logits.argmax(-1).cpu()
        for i, (tokens, (_, _, firsts)) in enumerate(zip(chunk, encs)):
            tags = [TAGS[tag_ids[i, firsts[w]]] if w in firsts else "O" for w in range(len(tokens))]
            out.append({"intent": INTENTS[int(probs[i].argmax())], "probs": probs[i].tolist(), "tags": tags})
    return out


def span_set(tokens, tags):
    """Gold or predicted spans as (start, end) word positions, for exact-match slot scoring."""
    spans, start = set(), None
    for i, tag in enumerate(list(tags) + ["O"]):
        if start is not None and tag != "I-TRAIT":
            spans.add((start, i))
            start = None
        if tag == "B-TRAIT" or (tag == "I-TRAIT" and start is None):
            start = i
    return spans


def f1(p, r):
    return 2 * p * r / max(p + r, 1e-9)


def scores(rows, preds):
    """Intent accuracy, and slot precision, recall and F1 by exact span match. The LLM chose span boundaries loosely
    (gold "talk circles around", predicted "talk circles around your entire team"), so two lenient slot F1s are given
    too: per tagged word, and per span where a span counts if it overlaps one on the other side."""
    correct = sum(p["intent"] == r["intent"] for r, p in zip(rows, preds))
    tp = n_pred = n_gold = 0
    wtp = w_pred = w_gold = 0
    o_pred = o_gold = 0
    for r, p in zip(rows, preds):
        g, q = span_set(r["tokens"], r["tags"]), span_set(r["tokens"], p["tags"])
        tp, n_pred, n_gold = tp + len(g & q), n_pred + len(q), n_gold + len(g)
        gw = {i for a, b in g for i in range(a, b)}
        qw = {i for a, b in q for i in range(a, b)}
        wtp, w_pred, w_gold = wtp + len(gw & qw), w_pred + len(qw), w_gold + len(gw)
        o_pred += sum(any(a < d and c < b for a, b in g) for c, d in q)
        o_gold += sum(any(a < d and c < b for c, d in q) for a, b in g)
    prec, rec = tp / max(n_pred, 1), tp / max(n_gold, 1)
    return {"n": len(rows), "intent_acc": correct / max(len(rows), 1), "slot_precision": prec, "slot_recall": rec,
            "slot_f1": f1(prec, rec), "slot_word_f1": f1(wtp / max(w_pred, 1), wtp / max(w_gold, 1)),
            "slot_overlap_f1": f1(o_pred / max(n_pred, 1), o_gold / max(n_gold, 1))}


def train(model, tok, train_rows, val_rows, device, out_dir, lr=5e-5, epochs=6, batch_size=16, patience=2,
          warmup=0.1, weight_decay=0.01, max_len=160, seed=42, max_batches=None, log=print):
    """Fine-tunes on train_rows and keeps the epoch with the best validation score, the mean of intent accuracy and
    per-word slot F1. Per word, not exact span: with the loose gold boundaries, exact-span F1 jumped by 0.02-0.03
    between epochs while per-word F1 hardly moved, so it picked epochs by noise. Returns the per-epoch history."""
    model.to(device)
    collate = make_collate(tok.pad_token_id)
    data = [example(tok, r, max_len) for r in train_rows]
    gen = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(data, batch_size, shuffle=True, collate_fn=collate, generator=gen)
    steps = epochs * (min(len(loader), max_batches) if max_batches else len(loader))
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    sched = get_linear_schedule_with_warmup(opt, int(warmup * steps), steps)
    ce = nn.CrossEntropyLoss(ignore_index=-100)
    history, best, bad = [], -1.0, 0
    for epoch in range(1, epochs + 1):
        model.train()
        t, total, n = time.time(), 0.0, 0
        for b, batch in enumerate(loader):
            if max_batches and b >= max_batches:
                break
            batch = {k: v.to(device) for k, v in batch.items()}
            intent_logits, tag_logits = model(batch["input_ids"], batch["attention_mask"])
            loss = ce(intent_logits, batch["intent"]) + ce(tag_logits.flatten(0, 1), batch["labels"].flatten())
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            total, n = total + loss.item(), n + 1
        val = scores(val_rows, predict(model, tok, [r["tokens"] for r in val_rows], device, max_len=max_len))
        score = (val["intent_acc"] + val["slot_word_f1"]) / 2
        history.append({"epoch": epoch, "train_loss": total / max(n, 1), **{f"val_{k}": v for k, v in val.items()},
                        "val_score": score, "seconds": time.time() - t})
        log(f"epoch {epoch}: train loss {total / max(n, 1):.4f} | val intent acc {val['intent_acc']:.3f} "
            f"slot F1 {val['slot_f1']:.3f} (per word {val['slot_word_f1']:.3f}) | {time.time() - t:.0f}s")
        if score > best:
            best, bad = score, 0
            save(model, tok, out_dir, {"epoch": epoch, "val": val})
        else:
            bad += 1
            if bad >= patience:
                log(f"no improvement for {patience} epochs, stopping")
                break
    json.dump(history, open(Path(out_dir) / "history.json", "w"), indent=2)
    log(f"best val score {best:.4f}, saved {out_dir}")
    return history


class NLU:
    """The trained model plus trait normalization: message -> intent and traits, for the dialogue manager."""

    def __init__(self, model, tok, normalizer=None, device="cpu"):
        self.model, self.tok, self.device = model, tok, device
        self._normalizer = normalizer

    @classmethod
    def load(cls, path, device="cpu", normalizer=None):
        model, tok = load(path, device)
        return cls(model, tok, normalizer, device)

    @property
    def normalizer(self):
        if self._normalizer is None:
            from .normalize import TraitNormalizer
            self._normalizer = TraitNormalizer()
        return self._normalizer

    def parse(self, text):
        tokens = TOKEN_RE.findall(text)
        if not tokens:
            return {"intent": "out_of_scope", "confidence": 0.0, "traits": []}
        p = predict(self.model, self.tok, [tokens], self.device)[0]
        # the tagger often splits one span around a word ("fluent | metaphor and sarcasm"); joining fragments one
        # word apart raised end-to-end trait accuracy on val
        merged = []
        for a, b in sorted(span_set(tokens, p["tags"])):
            if merged and a - merged[-1][1] <= MERGE_GAP:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        spans = [s for s in (" ".join(tokens[a:b]).strip(EDGE_PUNCT) for a, b in merged) if s]
        found = [{"span": s, **n} for s, n in zip(spans, self.normalizer.many(spans))] if spans else []
        return {"intent": p["intent"], "confidence": round(max(p["probs"]), 3), "traits": found}
