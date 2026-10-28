"""System A: GRU language model with the traits, intensity and rhyme words as a prefix (Week 4).

Training (both stages), checkpoints and sampling. Driven by generation/train_gru.ipynb; the app and the
reranker load a trained model with load_model() and sample with generate().
"""
import json, math, random, re, time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

from sequences import SequenceDataset, make_collate

WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)?")


class GRULM(nn.Module):
    def __init__(self, vocab_size, emb_dim=300, hidden=512, layers=2, dropout=0.3, pad_id=0):
        super().__init__()
        self.args = dict(vocab_size=vocab_size, emb_dim=emb_dim, hidden=hidden, layers=layers,
                         dropout=dropout, pad_id=pad_id)
        self.emb = nn.Embedding(vocab_size, emb_dim, padding_idx=pad_id)
        self.drop = nn.Dropout(dropout)
        self.gru = nn.GRU(emb_dim, hidden, layers, batch_first=True, dropout=dropout if layers > 1 else 0.0)
        self.out = nn.Linear(hidden, vocab_size)

    def forward(self, x, h=None):
        o, h = self.gru(self.drop(self.emb(x)), h)
        return self.out(self.drop(o)), h


def masked_loss(logits, target, mask):
    """Summed cross-entropy over poem tokens, and how many there were."""
    loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), target.reshape(-1), reduction="none")
    return (loss.view_as(mask) * mask).sum(), mask.sum()


def run_epoch(model, loader, device, opt=None, clip=1.0, max_batches=None):
    """One pass; trains when opt is given. Returns the mean loss per poem token."""
    model.train(opt is not None)
    total, count = 0.0, 0.0
    with torch.set_grad_enabled(opt is not None):
        for k, b in enumerate(loader):
            if max_batches and k >= max_batches:
                break
            logits, _ = model(b["input"].to(device))
            loss, n = masked_loss(logits, b["target"].to(device), b["mask"].to(device))
            if opt is not None:
                opt.zero_grad()
                (loss / n).backward()
                nn.utils.clip_grad_norm_(model.parameters(), clip)
                opt.step()
            total, count = total + loss.item(), count + n.item()
    return total / max(count, 1)


def save_checkpoint(path, model, **extra):
    torch.save({"model_state": model.state_dict(), "model_args": model.args, **extra}, path)


def load_model(path, device="cpu"):
    ck = torch.load(path, map_location=device)
    model = GRULM(**ck["model_args"]).to(device)
    model.load_state_dict(ck["model_state"])
    return model.eval(), ck


def train_stage(model, train_ex, val_ex, pad_id, device, ckpt_dir, name, lr, max_epochs, patience=3,
                batch_size=64, weight_decay=0.01, clip=1.0, seed=42, max_batches=None, resume=True, log=print):
    """Trains until validation loss stops improving (patience epochs), keeping the best checkpoint.

    Writes <name>_best.pt (best weights) and <name>_last.pt (everything needed to resume after a disconnect).
    Returns the history and leaves the best weights loaded in the model.
    """
    ckpt_dir = Path(ckpt_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    best_path, last_path = ckpt_dir / f"{name}_best.pt", ckpt_dir / f"{name}_last.pt"
    collate = make_collate(pad_id)
    g = torch.Generator().manual_seed(seed)
    train_dl = torch.utils.data.DataLoader(SequenceDataset(train_ex), batch_size, shuffle=True,
                                           collate_fn=collate, generator=g)
    val_dl = torch.utils.data.DataLoader(SequenceDataset(val_ex), batch_size, collate_fn=collate)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=1)
    start, best, bad, history = 1, math.inf, 0, []

    if resume and last_path.exists():
        ck = torch.load(last_path, map_location=device)
        model.load_state_dict(ck["model_state"])
        opt.load_state_dict(ck["opt_state"])
        sched.load_state_dict(ck["sched_state"])
        g.set_state(ck["rng_state"])
        start, best, bad, history = ck["epoch"] + 1, ck["best"], ck["bad"], ck["history"]
        log(f"resumed {name} after epoch {ck['epoch']} (best val {best:.4f})")

    for epoch in range(start, max_epochs + 1):
        if bad >= patience:
            break
        t = time.time()
        tr = run_epoch(model, train_dl, device, opt, clip, max_batches)
        va = run_epoch(model, val_dl, device, max_batches=max_batches)
        sched.step(va)
        improved = va < best
        if improved:
            best, bad = va, 0
            save_checkpoint(best_path, model, name=name, epoch=epoch, val_loss=va)
        else:
            bad += 1
        history.append({"epoch": epoch, "train_loss": tr, "val_loss": va, "val_ppl": math.exp(va),
                        "lr": opt.param_groups[0]["lr"], "seconds": round(time.time() - t, 1)})
        log(f"{name} epoch {epoch:2d} | train {tr:.4f} | val {va:.4f} (ppl {math.exp(va):6.2f}) | "
            f"lr {opt.param_groups[0]['lr']:.1e} | {time.time() - t:5.1f}s{'  *best' if improved else ''}")
        save_checkpoint(last_path, model, name=name, epoch=epoch, best=best, bad=bad, history=history,
                        opt_state=opt.state_dict(), sched_state=sched.state_dict(), rng_state=g.get_state())

    model.load_state_dict(torch.load(best_path, map_location=device)["model_state"])
    json.dump(history, open(ckpt_dir / f"{name}_history.json", "w"), indent=2)
    log(f"{name}: best val loss {best:.4f} (ppl {math.exp(best):.2f}), saved {best_path}")
    return history


@torch.no_grad()
def generate(model, codec, traits, intensity, end_words, n=10, temperature=0.8, top_p=0.9,
             rep_penalty=1.2, max_len=100, device="cpu"):
    """Samples n poems in one batch. Each result has its lines and the length-normalized log-probability
    of its tokens under the model (temperature 1, no penalty), for the reranker."""
    model.eval()
    prefix = torch.tensor([codec.prefix(list(traits), intensity, list(end_words))] * n, device=device)
    logits, h = model(prefix)
    logits = logits[:, -1]
    words = torch.tensor([bool(re.search("[a-z]", codec.sp.id_to_piece(i))) for i in range(codec.vocab_size)],
                         device=device)   # repetition penalty applies to words only, not <nl> or punctuation
    seen = torch.zeros(n, codec.vocab_size, dtype=torch.bool, device=device)
    out = [[] for _ in range(n)]
    logprob, done, lines = torch.zeros(n, device=device), torch.zeros(n, dtype=torch.bool, device=device), \
        torch.zeros(n, dtype=torch.long, device=device)

    for _ in range(max_len):
        raw = F.log_softmax(logits, -1)
        adj = logits.clone()
        pen = seen & words
        adj[pen] = torch.where(adj[pen] > 0, adj[pen] / rep_penalty, adj[pen] * rep_penalty)
        probs = F.softmax(adj / temperature, -1)
        sorted_p, idx = probs.sort(-1, descending=True)
        cut = sorted_p.cumsum(-1) - sorted_p > top_p          # nucleus: keep the smallest set reaching top_p
        sorted_p[cut] = 0
        tok = idx.gather(1, torch.multinomial(sorted_p, 1)).squeeze(1)
        tok = torch.where(done, torch.full_like(tok, codec.pad), tok)
        logprob += torch.where(done, torch.zeros_like(logprob), raw.gather(1, tok[:, None]).squeeze(1))
        for k in torch.nonzero(~done).flatten().tolist():
            out[k].append(tok[k].item())
        seen[torch.arange(n, device=device), tok] = True
        lines += (tok == codec.id["<nl>"]).long()
        done |= (tok == codec.eos) | (lines >= 4)              # stop at <eos>, or after a fourth line break
        if done.all():
            break
        logits, h = model(tok[:, None], h)
        logits = logits[:, -1]

    return [{"lines": codec.decode_lines(ids), "ids": ids, "logprob": lp,
             "norm_logprob": lp / max(len(ids), 1)}
            for ids, lp in zip(out, logprob.tolist())]


def last_word(line):
    w = WORD_RE.findall(line.lower())
    return w[-1] if w else ""


def sample_report(model, codec, prompts, device, n=4, show=3, seed=0, log=print, **gen_kwargs):
    """Generates n poems per prompt and measures form: share with exactly 4 lines, and share of lines that end
    on the requested rhyme word. prompts: list of dicts with traits, intensity, end_words."""
    torch.manual_seed(seed)
    random.seed(seed)
    four, hits, total, shown = 0, 0, 0, 0
    for p in prompts:
        for s in generate(model, codec, p["traits"], p["intensity"], p["end_words"], n=n, device=device,
                          **gen_kwargs):
            four += len(s["lines"]) == 4 and all(s["lines"])
            for line, want in zip(s["lines"], p["end_words"]):
                hits += last_word(line) == want
            total += 1
            if shown < show:
                shown += 1
                log(f"\n[{', '.join(p['traits']) or 'no traits'} | {p['intensity']} | "
                    f"rhymes {' '.join(p['end_words'])}]  logprob/token {s['norm_logprob']:.2f}")
                for line in s["lines"]:
                    log("   " + line)
    report = {"samples": total, "four_lines": four / total, "end_word_hit": hits / (4 * total)}
    log(f"\n{total} samples: {report['four_lines']:.1%} have 4 lines, "
        f"{report['end_word_hit']:.1%} of lines end on the requested rhyme word")
    return report
