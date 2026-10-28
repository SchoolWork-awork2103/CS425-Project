"""System A: GRU language model with the traits, intensity and rhyme words as a prefix (Week 4).

Training (both stages), checkpoints and sampling. Driven by generation/train_gru.ipynb; the app and the
reranker load a trained model with load_generator() and sample with generate().
"""
import json, math, random, re, sys, time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

from sequences import PoemCodec, SequenceDataset, make_collate

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


def load_generator(path, cfg=None, device="cpu"):
    """A trained model and the codec for its sequence format (checkpoints without "reverse" are forward)."""
    model, ck = load_model(path, device)
    return model, PoemCodec(cfg, reverse=ck.get("reverse", False))


def train_stage(model, train_ex, val_ex, pad_id, device, ckpt_dir, name, lr, max_epochs, patience=3,
                batch_size=64, weight_decay=0.01, clip=1.0, seed=42, max_batches=None, resume=True, extra=None,
                log=print):
    """Trains until validation loss stops improving (patience epochs), keeping the best checkpoint.

    Writes <name>_best.pt (best weights) and <name>_last.pt (everything needed to resume after a disconnect).
    extra (e.g. {"reverse": True}) is stored in both. Returns the history and leaves the best weights loaded.
    """
    extra = extra or {}
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
            save_checkpoint(best_path, model, name=name, epoch=epoch, val_loss=va, **extra)
        else:
            bad += 1
        history.append({"epoch": epoch, "train_loss": tr, "val_loss": va, "val_ppl": math.exp(va),
                        "lr": opt.param_groups[0]["lr"], "seconds": round(time.time() - t, 1)})
        log(f"{name} epoch {epoch:2d} | train {tr:.4f} | val {va:.4f} (ppl {math.exp(va):6.2f}) | "
            f"lr {opt.param_groups[0]['lr']:.1e} | {time.time() - t:5.1f}s{'  *best' if improved else ''}")
        save_checkpoint(last_path, model, name=name, epoch=epoch, best=best, bad=bad, history=history,
                        opt_state=opt.state_dict(), sched_state=sched.state_dict(), rng_state=g.get_state(), **extra)

    model.load_state_dict(torch.load(best_path, map_location=device)["model_state"])
    json.dump(history, open(ckpt_dir / f"{name}_history.json", "w"), indent=2)
    log(f"{name}: best val loss {best:.4f} (ppl {math.exp(best):.2f}), saved {best_path}")
    return history


@torch.no_grad()
def generate(model, codec, traits, intensity, end_words, n=10, temperature=0.8, top_p=0.9,
             rep_penalty=1.2, max_len=120, min_line_tokens=3, max_line_tokens=30, device="cpu"):
    """Samples n poems in one batch, always exactly four lines (no <eos> before line 4, no fifth line, lines of
    min_line_tokens to max_line_tokens). With a reversed-line codec the first word of each line is forced to its
    rhyme word and may not grow into a longer word, so every line ends on the plan.

    Each result has its lines and the length-normalized log-probability of its tokens under the model
    (temperature 1, no penalty, forced tokens included), for the reranker."""
    model.eval()
    V, nl, eos = codec.vocab_size, codec.id["<nl>"], codec.eos
    pieces = [codec.sp.id_to_piece(i) for i in range(V)]
    words = torch.tensor([bool(re.search("[a-z]", p)) for p in pieces], device=device)   # penalized on repeat
    # pieces that would glue letters onto the rhyme word ("hearts", "heart's", "heart-x", raw bytes)
    glue = torch.tensor([codec.sp.is_byte(i) or (i != nl and not p.startswith("▁") and bool(re.search("[a-z0-9']", p)))
                         for i, p in enumerate(pieces)], device=device)
    forced = [codec.sp.encode(w) for w in end_words] if codec.reverse else None

    prefix = torch.tensor([codec.prefix(list(traits), intensity, list(end_words))] * n, device=device)
    logits, h = model(prefix)
    logits = logits[:, -1]
    seen = torch.zeros(n, V, dtype=torch.bool, device=device)
    out, line, pos = [[] for _ in range(n)], [0] * n, [0] * n      # pos: tokens so far in the current line
    tail = [False] * n            # just after the forced rhyme word, before the next word starts
    logprob, done = torch.zeros(n, device=device), torch.zeros(n, dtype=torch.bool, device=device)

    for _ in range(max_len):
        raw = F.log_softmax(logits, -1)
        adj = logits.clone()
        pen = seen & words
        adj[pen] = torch.where(adj[pen] > 0, adj[pen] / rep_penalty, adj[pen] * rep_penalty)
        block = torch.zeros(n, V, dtype=torch.bool, device=device)
        for k in range(n):
            if pos[k] < min_line_tokens:
                block[k, nl] = block[k, eos] = True
            else:
                block[k, eos if line[k] < 3 else nl] = True
            if tail[k]:
                block[k] |= glue                                # the rhyme word stays whole
        adj[block] = float("-inf")
        probs = F.softmax(adj / temperature, -1)
        sorted_p, idx = probs.sort(-1, descending=True)
        cut = sorted_p.cumsum(-1) - sorted_p > top_p          # nucleus: keep the smallest set reaching top_p
        sorted_p[cut] = 0
        tok = idx.gather(1, torch.multinomial(sorted_p, 1)).squeeze(1)
        for k in range(n):
            if forced and pos[k] < len(forced[line[k]]):
                tok[k] = forced[line[k]][pos[k]]
            elif pos[k] >= max_line_tokens:                     # a runaway line is ended
                tok[k] = nl if line[k] < 3 else eos
        tok = torch.where(done, torch.full_like(tok, codec.pad), tok)
        logprob += torch.where(done, torch.zeros_like(logprob), raw.gather(1, tok[:, None]).squeeze(1))
        for k in torch.nonzero(~done).flatten().tolist():
            t = tok[k].item()
            out[k].append(t)
            if t == nl:
                line[k], pos[k], tail[k] = line[k] + 1, 0, False
            else:
                pos[k] += 1
                if forced and pos[k] == len(forced[line[k]]):
                    tail[k] = True
                elif pieces[t].startswith("▁"):
                    tail[k] = False
        seen[torch.arange(n, device=device), tok] = True
        done |= tok == eos
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


def rhyme_checker():
    """form_checks.rhymes (CMUdict), the same rule the datasets were filtered with; None if it can't be loaded."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data"))
    try:
        from form_checks import rhymes
        return rhymes
    except ImportError:
        return None


def sample_report(model, codec, prompts, device, n=4, show=3, seed=0, log=print, **gen_kwargs):
    """Generates n poems per prompt and measures form: share with exactly 4 lines, share of lines that end on
    the requested rhyme word, share of couplets that rhyme and share of full AABB poems.
    prompts: list of dicts with traits, intensity, end_words."""
    torch.manual_seed(seed)
    random.seed(seed)
    rhymes = rhyme_checker()
    four = hits = pairs = aabb = total = shown = 0
    for p in prompts:
        for s in generate(model, codec, p["traits"], p["intensity"], p["end_words"], n=n, device=device,
                          **gen_kwargs):
            lines = s["lines"]
            ends = [last_word(l) for l in lines]
            four += len(lines) == 4 and all(lines)
            hits += sum(e == w for e, w in zip(ends, p["end_words"]))
            if rhymes and len(ends) == 4:
                ok = [rhymes(ends[0], ends[1]), rhymes(ends[2], ends[3])]
                pairs, aabb = pairs + sum(ok), aabb + all(ok)
            total += 1
            if shown < show:
                shown += 1
                log(f"\n[{', '.join(p['traits']) or 'no traits'} | {p['intensity']} | "
                    f"rhymes {' '.join(p['end_words'])}]  logprob/token {s['norm_logprob']:.2f}")
                for l in lines:
                    log("   " + l)
    report = {"samples": total, "four_lines": four / total, "end_word_hit": hits / (4 * total)}
    if rhymes:
        report.update(couplets_rhyme=pairs / (2 * total), aabb=aabb / total)
    log(f"\n{total} samples: {report['four_lines']:.1%} have 4 lines | {report['end_word_hit']:.1%} of lines end "
        f"on the requested rhyme word" + (f" | {report['couplets_rhyme']:.1%} of couplets rhyme | "
                                          f"{report['aabb']:.1%} full AABB" if rhymes else ""))
    return report
