"""System D: Qwen2.5-Instruct with LoRA adapters, fine-tuned on the disses (Week 10).

The prompt carries the same information as System A's prefix (traits, intensity and the four planned end words), as
a chat message. The answer is four lines, each tagged with its end word first:

    [late] you live by your clock, not a minute too late,
    [wait] your life's all in stock tips and nothing to wait.

The tag makes the model commit to the rhyme word before it writes the line, as in the quatrain generation
(quatrain_gen.ipynb); decode_lines strips it. Lines are written forward, so unlike System A nothing forces the end
word: report() measures how often it lands. The loss covers the answer only.

Training and sampling. Driven by generation/train_qwen.ipynb; the app and the reranker load a trained adapter with
load_generator() and sample with generate().
"""
import contextlib, json, math, re, sys, time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model, get_peft_model_state_dict, set_peft_model_state_dict
from safetensors.torch import load_file
from transformers import (AutoModelForCausalLM, AutoTokenizer, LogitsProcessor, LogitsProcessorList,
                          get_cosine_schedule_with_warmup)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from phonetics import last_word, lexical_score, rhymes, syllable_score, words_of

SYSTEM = ("You write short, playful roasts: four-line AABB quatrains where lines 1-2 rhyme and lines 3-4 rhyme. "
          "Stay on the given traits and never insult appearance, race, religion, gender or disability. "
          "Start each line with its end word in square brackets.")
TAG_RE = re.compile(r"^\s*\[[^\]]*\]\s*")


def user_message(traits, intensity, end_words):
    return f"Traits: {', '.join(traits) or 'none'}\nIntensity: {intensity}\nEnd words: {', '.join(end_words)}"


def answer_text(lines, end_words):
    return "\n".join(f"[{w}] {l}" for w, l in zip(end_words, lines))


def decode_lines(text):
    """Model answer -> its first four lines, tags stripped (the pipeline stops after the fourth line)."""
    return [TAG_RE.sub("", l).strip() for l in text.strip().split("\n") if l.strip()][:4]


def prompt_ids(tok, traits, intensity, end_words):
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_message(list(traits), intensity, list(end_words))}]
    return tok(tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True),
               add_special_tokens=False).input_ids


def example(tok, row):
    p = prompt_ids(tok, row["traits"], row["intensity"], row["end_words"])
    a = tok(answer_text(row["lines"], row["end_words"]), add_special_tokens=False).input_ids
    a.append(tok.convert_tokens_to_ids("<|im_end|>"))
    return {"ids": p + a, "labels": [-100] * len(p) + a}


def make_collate(pad_id):
    def collate(batch):
        n = max(len(b["ids"]) for b in batch)
        ids = torch.full((len(batch), n), pad_id)
        labels = torch.full((len(batch), n), -100)
        att = torch.zeros(len(batch), n, dtype=torch.long)
        for k, b in enumerate(batch):
            ids[k, :len(b["ids"])], labels[k, :len(b["ids"])] = torch.tensor(b["ids"]), torch.tensor(b["labels"])
            att[k, :len(b["ids"])] = 1
        return {"input_ids": ids, "attention_mask": att, "labels": labels}
    return collate


def half_dtype(device):
    """bf16 where the GPU has it (L40S, A100), fp16 on a T4, fp32 on the CPU."""
    if device != "cuda":
        return torch.float32
    try:
        bf16 = torch.cuda.is_bf16_supported(including_emulation=False)
    except TypeError:
        bf16 = torch.cuda.is_bf16_supported()
    return torch.bfloat16 if bf16 else torch.float16


def autocast(device):
    return torch.autocast("cuda", dtype=half_dtype(device)) if device == "cuda" else contextlib.nullcontext()


def load_base(name, device="cpu"):
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForCausalLM.from_pretrained(name, dtype=half_dtype(device)).to(device)
    return model, tok


def add_lora(model, r=16, alpha=32, dropout=0.05, targets=("q_proj", "k_proj", "v_proj", "o_proj")):
    model = get_peft_model(model, LoraConfig(r=r, lora_alpha=alpha, lora_dropout=dropout,
                                             target_modules=list(targets), task_type="CAUSAL_LM"))
    for p in model.parameters():
        if p.requires_grad:
            p.data = p.data.float()          # the adapters train in fp32 under autocast; the frozen base stays half
    return model


def load_generator(adapter_dir, device="cpu"):
    """A trained adapter on its base model (named in adapter_config.json), and the tokenizer."""
    base = json.load(open(Path(adapter_dir) / "adapter_config.json"))["base_model_name_or_path"]
    model, tok = load_base(base, device)
    return PeftModel.from_pretrained(model, str(adapter_dir)).eval(), tok


def run_epoch(model, loader, device, opt=None, sched=None, scaler=None, accum=1, clip=1.0, max_batches=None,
              log=None, log_every=50):
    """Mean loss per answer token; trains when opt is given (gradients accumulated over accum batches)."""
    train = opt is not None
    model.train(train)
    n = min(len(loader), max_batches or len(loader))
    total, count, t = 0.0, 0, time.time()
    with torch.set_grad_enabled(train):
        for i, batch in enumerate(loader):
            if i >= n:
                break
            batch = {k: v.to(device) for k, v in batch.items()}
            with autocast(device):
                loss = model(**batch).loss
            k = (batch["labels"][:, 1:] != -100).sum().item()
            total, count = total + loss.item() * k, count + k
            if train:
                scaler.scale(loss / accum).backward()
                if (i + 1) % accum == 0 or i + 1 == n:
                    scaler.unscale_(opt)
                    torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], clip)
                    scaler.step(opt)
                    scaler.update()
                    opt.zero_grad(set_to_none=True)
                    sched.step()
                if log and (i + 1) % log_every == 0:
                    s = time.time() - t
                    log(f"  batch {i + 1}/{n} | loss {total / count:.4f} | {s / 60:.1f} min, "
                        f"about {s / (i + 1) * (n - i - 1) / 60:.1f} min left in the epoch")
    return total / max(count, 1)


def train(model, tok, train_ex, val_ex, device, ckpt_dir, name, lr=2e-4, epochs=3, batch_size=8, accum=2,
          warmup=0.05, weight_decay=0.0, clip=1.0, seed=42, max_batches=None, resume=True, log=print):
    """Trains the adapters for a fixed number of epochs on a cosine schedule, keeping the epoch with the best
    validation loss.

    Writes <name>_best/ (the adapter, in peft format) and <name>_last.pt (adapter, optimizer and schedule, to resume
    after a disconnect). Returns the history and leaves the best adapter loaded.
    """
    ckpt_dir = Path(ckpt_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    best_dir, last_path = ckpt_dir / f"{name}_best", ckpt_dir / f"{name}_last.pt"
    collate = make_collate(tok.pad_token_id)
    val_dl = torch.utils.data.DataLoader(val_ex, batch_size * 2, collate_fn=collate)
    batches = min(math.ceil(len(train_ex) / batch_size), max_batches or math.inf)
    total_steps = math.ceil(batches / accum) * epochs
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr, weight_decay=weight_decay)
    sched = get_cosine_schedule_with_warmup(opt, int(warmup * total_steps), total_steps)
    scaler = torch.amp.GradScaler(device, enabled=half_dtype(device) == torch.float16)
    start, best, history = 1, math.inf, []

    if resume and last_path.exists():
        ck = torch.load(last_path, map_location=device)
        set_peft_model_state_dict(model, ck["adapter"])
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        scaler.load_state_dict(ck["scaler"])
        start, best, history = ck["epoch"] + 1, ck["best"], ck["history"]
        log(f"resumed {name} after epoch {ck['epoch']} (best val {best:.4f})")

    for epoch in range(start, epochs + 1):
        g = torch.Generator().manual_seed(seed + epoch)      # per-epoch order, so a resumed run sees the same batches
        train_dl = torch.utils.data.DataLoader(train_ex, batch_size, shuffle=True, collate_fn=collate, generator=g)
        t = time.time()
        tr = run_epoch(model, train_dl, device, opt, sched, scaler, accum, clip, max_batches, log)
        va = run_epoch(model, val_dl, device, max_batches=max_batches)
        improved = va < best
        if improved:
            best = va
            model.save_pretrained(best_dir)
        history.append({"epoch": epoch, "train_loss": tr, "val_loss": va, "val_ppl": math.exp(va),
                        "lr": opt.param_groups[0]["lr"], "seconds": round(time.time() - t, 1)})
        log(f"{name} epoch {epoch} | train {tr:.4f} | val {va:.4f} (ppl {math.exp(va):.2f}) | "
            f"{(time.time() - t) / 60:.1f} min{'  *best' if improved else ''}")
        torch.save({"adapter": get_peft_model_state_dict(model), "opt": opt.state_dict(), "sched": sched.state_dict(),
                    "scaler": scaler.state_dict(), "epoch": epoch, "best": best, "history": history}, last_path)

    set_peft_model_state_dict(model, load_file(best_dir / "adapter_model.safetensors", device=device))
    json.dump(history, open(ckpt_dir / f"{name}_history.json", "w"), indent=2)
    log(f"{name}: best val loss {best:.4f} (ppl {math.exp(best):.2f}), saved {best_dir}")
    return history


class AnswerRepetitionPenalty(LogitsProcessor):
    """System A's repetition penalty: word tokens already in the answer are penalized. The prompt is left out (it
    lists the end words), and so are the end words, which each appear twice (tag and line end)."""

    def __init__(self, penalized, prompt_len, penalty):
        self.penalized, self.prompt_len, self.penalty = penalized, prompt_len, penalty

    def __call__(self, input_ids, scores):
        answer = input_ids[:, self.prompt_len:]
        if answer.shape[1] == 0 or self.penalty == 1:
            return scores
        seen = torch.zeros_like(scores, dtype=torch.bool).scatter_(1, answer, True) & self.penalized
        s = scores[seen]
        scores[seen] = torch.where(s > 0, s / self.penalty, s * self.penalty)
        return scores


def penalized_tokens(tok, vocab_size, end_words, device):
    pieces = tok.convert_ids_to_tokens(list(range(len(tok))))
    words = [bool(re.search("[a-z]", p.lower())) for p in pieces] + [False] * (vocab_size - len(tok))
    mask = torch.tensor(words, device=device)
    for w in end_words:
        for text in (w, " " + w, f"[{w}]"):
            mask[tok(text, add_special_tokens=False).input_ids] = False
    return mask


@torch.no_grad()
def generate(model, tok, traits, intensity, end_words, n=10, temperature=0.8, top_p=0.9, rep_penalty=1.2,
             max_new_tokens=160, device="cpu"):
    """Samples n answers in one batch. Each result has its lines (tags stripped, at most four) and the
    length-normalized log-probability of its tokens under the model (temperature 1, no penalty), for the reranker."""
    model.eval()
    prompt = torch.tensor([prompt_ids(tok, traits, intensity, end_words)], device=device)
    penalty = AnswerRepetitionPenalty(penalized_tokens(tok, model.config.vocab_size, end_words, device),
                                      prompt.shape[1], rep_penalty)
    with autocast(device):
        out = model.generate(input_ids=prompt, attention_mask=torch.ones_like(prompt), do_sample=True,
                             temperature=temperature, top_p=top_p, top_k=0, repetition_penalty=1.0,
                             num_return_sequences=n, max_new_tokens=max_new_tokens, pad_token_id=tok.pad_token_id,
                             logits_processor=LogitsProcessorList([penalty]), output_logits=True,
                             return_dict_in_generate=True)
    answer = out.sequences[:, prompt.shape[1]:]
    lp = torch.stack([l.float().log_softmax(-1).gather(1, answer[:, j, None]).squeeze(1)
                      for j, l in enumerate(out.logits)], 1)
    eos = torch.isin(answer, torch.tensor(model.generation_config.eos_token_id, device=device).flatten())
    valid = (eos.cumsum(1) - eos.int()) == 0                      # up to and including the first end token
    logprob, length = (lp * valid).sum(1), valid.sum(1).clamp(min=1)
    texts = tok.batch_decode(answer, skip_special_tokens=True)
    return [{"lines": decode_lines(t), "text": t, "logprob": l, "norm_logprob": l / k}
            for t, l, k in zip(texts, logprob.tolist(), length.tolist())]


def report(prompts, poems, trait_info, show=0, log=print):
    """Form and content checks on any system's poems, so A and D are measured the same way. poems[i] is the list of
    samples (each a list of lines) for prompts[i]; trait_info is data/traits.json, for the synonyms.

    four_lines, end_word_hit, couplets_rhyme and aabb match gru_lm.sample_report; trait_mention is the share of
    poems naming one of their traits or its synonyms; distinct_2 is over all poems together."""
    four = hits = pairs = aabb = total = mention = with_traits = shown = 0
    syl, lex, bigrams = [], [], []
    for p, samples in zip(prompts, poems):
        terms = [t for tr in p["traits"] for t in [tr, *trait_info.get(tr, {}).get("synonyms", [])]]
        for lines in samples:
            ends = [last_word(l) for l in lines]
            four += len(lines) == 4 and all(lines)
            hits += sum(e == w for e, w in zip(ends, p["end_words"]))
            if len(ends) == 4:
                ok = [rhymes(ends[0], ends[1]), rhymes(ends[2], ends[3])]
                pairs, aabb = pairs + sum(ok), aabb + all(ok)
            syl.append(syllable_score(lines))
            lex.append(lexical_score(lines) if lines else 0.0)
            text = " ".join(lines).lower()
            if terms:
                with_traits += 1
                mention += any(re.search(rf"\b{re.escape(t)}\b", text) for t in terms)
            w = words_of(text)
            bigrams += list(zip(w, w[1:]))
            total += 1
            if shown < show:
                shown += 1
                log(f"\n[{', '.join(p['traits']) or 'no traits'} | {p['intensity']} | "
                    f"rhymes {' '.join(p['end_words'])}]")
                for l in lines:
                    log("   " + l)
    r = {"samples": total, "four_lines": four / total, "end_word_hit": hits / (4 * total),
         "couplets_rhyme": pairs / (2 * total), "aabb": aabb / total, "syllables": sum(syl) / total,
         "lexical": sum(lex) / total, "trait_mention": mention / max(with_traits, 1),
         "distinct_2": len(set(bigrams)) / max(len(bigrams), 1)}
    log(f"\n{total} samples: {r['four_lines']:.1%} have 4 lines | {r['end_word_hit']:.1%} of lines end on the "
        f"requested rhyme word | {r['couplets_rhyme']:.1%} of couplets rhyme | {r['aabb']:.1%} full AABB | "
        f"{r['trait_mention']:.1%} name a trait")
    return r
