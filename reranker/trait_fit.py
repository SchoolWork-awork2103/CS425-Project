"""Phase 5: trait-fit classifier for the reranker. DistilBERT on "[traits] [SEP] [poem]" with two classes: the poem
roasts these traits, or it doesn't.

Positives are the disses (data/disses/corpus/) with their own traits; the generic fallback disses have no traits and
are left out. Negatives are the 1e set (data/negatives/corpus/negatives.jsonl) plus disses with shuffled lines:
  flat, non_rhyming, off_topic   split 80/10/10 within each type
  wrong_trait                    1e built these from train disses, so they stay in train; val and test get their own,
                                 relabelled from their own disses with the same rule (never a trait in the label's
                                 CLOSE group) and at the train ratio
  shuffled                       disses with their lines reordered so neither couplet stays together, in every split
The held-out-trait disses are in test only. Test adds two kinds of wrong_trait for them: a held-out diss with a
training trait, and a training-trait diss with a held-out trait, so held-out traits are tested as label and as poem.

Each trait is written out with its synonyms and flip side from traits.json ("describe_traits" in config.yaml), so a
held-out trait the model never saw in training still comes with words it knows.

Training and evaluation: python reranker/train_trait_fit.py. The reranker loads the trained model with

    fit = TraitFit.load("checkpoints/trait_fit_best")
    fit.score(["confident"], [poem_lines, ...])  -> [0.97, 0.03, ...]   # P(the poem roasts these traits)
"""
import contextlib, itertools, json, random, sys, time
from collections import defaultdict
from pathlib import Path

import torch
from torch import nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))                          # project root: utils
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "negatives"))   # the CLOSE trait groups
from utils import load_config, project_path
from prepare_negatives import close_to

SPLITS = ("train", "val", "test")
# line orders where neither couplet stays together (lines 1-2 or 3-4 in the same couplet slot), so a shuffled diss
# loses its setup-then-flip order and its AABB shape as written
SHUFFLES = [p for p in itertools.permutations(range(4)) if {p[0], p[1]} not in ({0, 1}, {2, 3})]
META = "trait_fit.json"


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def trait_text(traits, info, describe=True):
    """The first segment. With describe, each trait with its synonyms and flip side:
    "confident: self-assured, bold, sure of myself, cocky, arrogant, all talk"."""
    if not describe:
        return ", ".join(traits)
    return "; ".join(f"{t}: {', '.join(info[t]['synonyms'])}, {info[t]['flip']}" if t in info else t for t in traits)


def poem_text(lines):
    """The second segment: the four lines, with a slash at each line break."""
    if isinstance(lines, str):
        lines = [l for l in lines.split("\n") if l.strip()]
    return " / ".join(l.strip() for l in lines)


def _row(kind, traits, lines, heldout, about=None):
    return {"type": kind, "label": int(kind == "positive"), "traits": list(traits), "lines": list(lines),
            "about": about, "heldout": bool(heldout & (set(traits) | set(about or [])))}


def _relabel(disses, labels, rng, heldout):
    """wrong_trait: each diss labelled with one trait from `labels`, never one close to a trait it was written for."""
    out = []
    for d in disses:
        near = set().union(*(close_to(t) for t in d["traits"]))
        out.append(_row("wrong_trait", [rng.choice([t for t in labels if t not in near])], d["lines"], heldout,
                        about=d["traits"]))
    return out


def _shuffled(disses, rng, heldout):
    return [_row("shuffled", d["traits"], [d["lines"][i] for i in rng.choice(SHUFFLES)], heldout) for d in disses]


def build_splits(cfg, seed=None):
    """Train, val and test rows ({type, label, traits, lines, about, heldout}), the same for the same seed."""
    rng = random.Random(cfg["seed"] if seed is None else seed)
    hp = cfg["trait_fit"]
    info = json.load(open(project_path(cfg["paths"]["traits"]), encoding="utf-8"))
    heldout = {t for t, v in info.items() if v["heldout"]}
    train_traits = [t for t, v in info.items() if not v["heldout"]]
    diss_dir = project_path(cfg["paths"]["diss_dir"])
    disses = {s: [d for d in read_jsonl(diss_dir / f"{s}.jsonl") if d["traits"]] for s in SPLITS}
    seen = {s: [d for d in disses[s] if not set(d["traits"]) & heldout] for s in SPLITS}
    rows = {s: [_row("positive", d["traits"], d["lines"], heldout) for d in disses[s]] for s in SPLITS}

    by_type = defaultdict(list)
    for n in read_jsonl(project_path(cfg["paths"]["negatives_dir"]) / "negatives.jsonl"):
        by_type[n["type"]].append(_row(n["type"], n["traits"], n["lines"], heldout, n.get("about")))
    wrong = by_type.pop("wrong_trait", [])
    rows["train"] += wrong
    a, b, _ = cfg["data"]["diss_split"]
    for kind in sorted(by_type):
        group = by_type[kind]
        rng.shuffle(group)
        i, j = round(a * len(group)), round((a + b) * len(group))
        for s, part in zip(SPLITS, (group[:i], group[i:j], group[j:])):
            rows[s] += part

    ratio = len(wrong) / max(len(seen["train"]), 1)
    for s in ("val", "test"):
        rows[s] += _relabel(rng.sample(seen[s], min(round(ratio * len(seen[s])), len(seen[s]))), train_traits, rng,
                            heldout)
    for s in SPLITS:
        k = min(round(hp["shuffled_frac"] * len(seen[s])), len(seen[s]))
        rows[s] += _shuffled(rng.sample(seen[s], k), rng, heldout)

    held = [d for d in disses["test"] if set(d["traits"]) & heldout]
    rows["test"] += _relabel(held, train_traits, rng, heldout)
    rows["test"] += _relabel(rng.sample(seen["test"], min(len(held), len(seen["test"]))), sorted(heldout), rng,
                             heldout)
    rows["test"] += _shuffled(rng.sample(held, round(hp["shuffled_frac"] * len(held))), rng, heldout)
    for s in SPLITS:
        rng.shuffle(rows[s])
    return rows, info


def encode(tok, rows, info, describe=True, max_len=192):
    enc = tok([trait_text(r["traits"], info, describe) for r in rows], [poem_text(r["lines"]) for r in rows],
              truncation=True, max_length=max_len)
    return enc["input_ids"]


def make_collate(pad_id):
    def collate(batch):
        n = max(len(ids) for ids, _ in batch)
        ids = torch.full((len(batch), n), pad_id)
        mask = torch.zeros((len(batch), n), dtype=torch.long)
        for i, (x, _) in enumerate(batch):
            ids[i, :len(x)] = torch.tensor(x)
            mask[i, :len(x)] = 1
        return {"input_ids": ids, "attention_mask": mask, "labels": torch.tensor([y for _, y in batch])}
    return collate


def _autocast(device):
    # fp16 on the GPU (a T4 has fp16 tensor cores but no bf16); full precision on the CPU
    return torch.autocast("cuda", dtype=torch.float16) if device == "cuda" else contextlib.nullcontext()


def build(model_name):
    return (AutoModelForSequenceClassification.from_pretrained(model_name, num_labels=2),
            AutoTokenizer.from_pretrained(model_name))


def save(model, tok, out_dir, info, hp, extra=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    # the trait descriptions travel with the model, so scoring uses the same text it was trained on
    json.dump({"base_model": hp["model"], "describe_traits": hp["describe_traits"], "max_len": hp["max_len"],
               "traits": {t: {"synonyms": v["synonyms"], "flip": v["flip"]} for t, v in info.items()}, **(extra or {})},
              open(out_dir / META, "w"), indent=2)


def load(path, device="cpu"):
    path = Path(path)
    model = AutoModelForSequenceClassification.from_pretrained(path).to(device).eval()
    return model, AutoTokenizer.from_pretrained(path), json.load(open(path / META))


@torch.no_grad()
def predict(model, tok, rows, info, device, describe=True, max_len=192, batch_size=64):
    """P(fit) for each row."""
    model.eval()
    collate = make_collate(tok.pad_token_id)
    ids = encode(tok, rows, info, describe, max_len)
    out = []
    for s in range(0, len(ids), batch_size):
        batch = collate([(x, 0) for x in ids[s:s + batch_size]])
        with _autocast(device):
            logits = model(input_ids=batch["input_ids"].to(device), attention_mask=batch["attention_mask"].to(device)).logits
        out += logits.float().softmax(-1)[:, 1].cpu().tolist()
    return out


def auc(labels, scores):
    """ROC AUC: the chance that a random positive scores above a random negative (ties count half)."""
    pairs = sorted(zip(scores, labels))
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    if not n_pos or not n_neg:
        return float("nan")
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        rank_sum += (i + j + 1) / 2 * sum(y for _, y in pairs[i:j])   # mean 1-based rank of the tied block
        i = j
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def scores(rows, probs, threshold=0.5):
    """AUC, accuracy, precision, recall and F1 at the threshold, and per row type the mean score and the share scored
    as a fit (for positives that is recall; for a negative type, how often it gets through)."""
    y = [r["label"] for r in rows]
    pred = [p >= threshold for p in probs]
    tp = sum(p and t for p, t in zip(pred, y))
    prec, rec = tp / max(sum(pred), 1), tp / max(sum(y), 1)
    by_type = defaultdict(list)
    for r, p in zip(rows, probs):
        by_type[r["type"]].append(p)
    return {"n": len(rows), "positives": sum(y), "auc": auc(y, probs),
            "accuracy": sum(p == bool(t) for p, t in zip(pred, y)) / max(len(y), 1),
            "precision": prec, "recall": rec, "f1": 2 * prec * rec / max(prec + rec, 1e-9),
            "by_type": {k: {"n": len(v), "mean_score": sum(v) / len(v), "scored_fit": sum(p >= threshold for p in v) / len(v)}
                        for k, v in sorted(by_type.items())}}


def train(model, tok, train_rows, val_rows, info, hp, device, out_dir, lr=None, epochs=None, seed=42,
          max_batches=None, log=print):
    """Fine-tunes on train_rows and keeps the epoch with the best val AUC (the reranker only uses the score's order).
    Returns the per-epoch history."""
    lr, epochs = lr or hp["lr"], epochs or hp["epochs"]
    model.to(device)
    ids = encode(tok, train_rows, info, hp["describe_traits"], hp["max_len"])
    data = list(zip(ids, [r["label"] for r in train_rows]))
    gen = torch.Generator().manual_seed(seed)
    loader = torch.utils.data.DataLoader(data, hp["batch_size"], shuffle=True, collate_fn=make_collate(tok.pad_token_id),
                                         generator=gen)
    steps = epochs * (min(len(loader), max_batches) if max_batches else len(loader))
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=hp["weight_decay"])
    sched = get_linear_schedule_with_warmup(opt, int(hp["warmup"] * steps), steps)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    ce = nn.CrossEntropyLoss()
    history, best, bad = [], -1.0, 0
    for epoch in range(1, epochs + 1):
        model.train()
        t, total, n = time.time(), 0.0, 0
        for b, batch in enumerate(loader):
            if max_batches and b >= max_batches:
                break
            batch = {k: v.to(device) for k, v in batch.items()}
            with _autocast(device):
                logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).logits
            loss = ce(logits.float(), batch["labels"])
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
            total, n = total + loss.item(), n + 1
        val = scores(val_rows, predict(model, tok, val_rows, info, device, hp["describe_traits"], hp["max_len"]))
        history.append({"epoch": epoch, "train_loss": total / max(n, 1),
                        **{f"val_{k}": v for k, v in val.items() if k != "by_type"}, "seconds": time.time() - t})
        log(f"epoch {epoch}: train loss {total / max(n, 1):.4f} | val AUC {val['auc']:.4f} acc {val['accuracy']:.3f} "
            f"F1 {val['f1']:.3f} | {time.time() - t:.0f}s")
        if val["auc"] > best:
            best, bad = val["auc"], 0
            save(model, tok, out_dir, info, hp, {"epoch": epoch, "lr": lr, "seed": seed, "val": val})
        else:
            bad += 1
            if bad >= hp["patience"]:
                log(f"no improvement for {hp['patience']} epochs, stopping")
                break
    json.dump(history, open(Path(out_dir) / "history.json", "w"), indent=2)
    log(f"best val AUC {best:.4f}, saved {out_dir}")
    return history


class TraitFit:
    """The trained classifier, for the reranker: P(a poem roasts the given traits)."""

    def __init__(self, model, tok, meta, device="cpu"):
        self.model, self.tok, self.meta, self.device = model, tok, meta, device

    @classmethod
    def load(cls, path=None, device="cpu"):
        path = path or project_path(load_config()["paths"]["checkpoints"]) / "trait_fit_best"
        model, tok, meta = load(path, device)
        return cls(model, tok, meta, device)

    def score(self, traits, poems, batch_size=64):
        """One score in [0, 1] per poem; a poem is its four lines, or one string with a line per row."""
        rows = [{"traits": list(traits), "lines": [l for l in p.split("\n") if l.strip()] if isinstance(p, str) else p}
                for p in poems]
        return predict(self.model, self.tok, rows, self.meta["traits"], self.device, self.meta["describe_traits"],
                       self.meta["max_len"], batch_size)
