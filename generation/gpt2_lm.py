"""System E: GPT-2 small (124M) checkpoints already fine-tuned on poetry, fully fine-tuned on the quatrains and then
the disses (pipeline_gpt2.md). The checkpoints are listed under gpt2.models in config.yaml; all three share GPT-2's
tokenizer.

The prompt carries the same information as Systems A and D (traits, intensity and the four planned end words), and the
poem is four lines, each tagged with its end word first, as in System D:

    Traits: lazy, funny
    Intensity: harsh
    Rhymes: late wait routine scene
    Poem:
    [late] you live by your clock, not a minute too late,
    [wait] ...<|endoftext|>

Stage 1 quatrains have traits "none" and intensity "none", as in System A. The tag makes the model commit to the rhyme
word before it writes the line; decode_lines strips it. Lines are written forward, so nothing forces the end word.
The loss covers the poem only, and an example longer than max_len is skipped rather than truncated, so the last
couplet never loses its rhyme.

Training and sampling. load_base() loads a Hugging Face checkpoint or a saved <name>_best/ directory alike.
"""
import json, math, re, shutil, sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, LogitsProcessor, LogitsProcessorList

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import load_config, project_path

STAGE_FILES = {                     # stage -> split -> (config path key, file name), as in sequences.STAGE_FILES
    1: {"train": ("corpus_dir", "quatrains_train.jsonl"), "val": ("corpus_dir", "quatrains_val.jsonl")},
    2: {"train": ("diss_dir", "train.jsonl"), "val": ("diss_dir", "val.jsonl"), "test": ("diss_dir", "test.jsonl")},
}
TAG_RE = re.compile(r"^\s*\[[^\]]*\]\s*")


def prompt_text(traits, intensity, end_words):
    return f"Traits: {', '.join(traits) or 'none'}\nIntensity: {intensity}\nRhymes: {' '.join(end_words)}\nPoem:\n"


def answer_text(lines, end_words):
    return "\n".join(f"[{w}] {l}" for w, l in zip(end_words, lines))


def decode_lines(text):
    """Generated text -> its first four lines, tags stripped."""
    return [TAG_RE.sub("", l).strip() for l in text.strip().split("\n") if l.strip()][:4]


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_split(stage, split, cfg=None):
    """(prompt, completion) pairs. Stage 1: quatrains (traits and intensity "none"). Stage 2: disses with their traits
    and intensity."""
    cfg = cfg or load_config()
    key, name = STAGE_FILES[stage][split]
    pairs = []
    for r in read_jsonl(project_path(cfg["paths"][key]) / name):
        if stage == 1:
            traits, intensity, end_words = [], "none", [w for p in r["rhymes"] for w in p]
        else:
            traits, intensity, end_words = r["traits"], r["intensity"], r["end_words"]
        pairs.append((prompt_text(traits, intensity, end_words), answer_text(r["lines"], end_words)))
    return pairs


def load_base(name, device="cpu"):
    tok = AutoTokenizer.from_pretrained(name)
    if tok.eos_token_id is None:
        raise ValueError(f"{name} has no end-of-text token")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(name).to(device)
    model.config.pad_token_id = tok.pad_token_id
    return model, tok


def encode(tok, prompt, completion, max_len):
    """One training example, or None when it is longer than max_len."""
    p = tok.encode(prompt, add_special_tokens=False)
    c = tok.encode(completion, add_special_tokens=False) + [tok.eos_token_id]
    if len(p) + len(c) > max_len:
        return None
    return {"input_ids": p + c, "attention_mask": [1] * (len(p) + len(c)), "labels": [-100] * len(p) + c}


def encode_all(tok, pairs, max_len):
    """(prompt, completion) pairs -> examples, and how many were skipped for length."""
    examples = [e for p, c in pairs if (e := encode(tok, p, c, max_len)) is not None]
    if not examples:
        raise ValueError(f"no example fits in {max_len} tokens")
    return examples, len(pairs) - len(examples)


def make_collate(pad_id):
    """Right-pads a batch; padding is masked out of attention and the loss."""
    def collate(batch):
        n = max(len(b["input_ids"]) for b in batch)
        return {k: torch.tensor([b[k] + [v] * (n - len(b[k])) for b in batch])
                for k, v in (("input_ids", pad_id), ("attention_mask", 0), ("labels", -100))}
    return collate


def epoch_history(log_history):
    """The Trainer's log -> one row per epoch, as in gen_D_*_history.json. train() logs the epoch's mean train loss
    once per epoch, just before evaluating."""
    rows, losses = [], []
    for e in log_history:
        if "loss" in e:
            losses.append(e["loss"])
        if "eval_loss" in e:
            rows.append({"epoch": round(e["epoch"]), "train_loss": sum(losses) / len(losses) if losses else None,
                         "val_loss": e["eval_loss"], "val_ppl": math.exp(e["eval_loss"])})
            losses = []
    return rows


def train(model, tok, train_ex, val_ex, ckpt_dir, name, lr=5e-5, epochs=5, patience=2, batch_size=8, accum=2,
          gradient_checkpointing=False, seed=42, run_root=None, log=print):
    """Full fine-tune, validating every epoch and stopping after `patience` epochs without improvement.

    Writes <name>_best/ (model and tokenizer, loadable with load_base) and <name>_history.json to ckpt_dir. The
    Trainer's epoch checkpoints (model only, about 0.5 GB each) go to <name>_run/ in run_root (default ckpt_dir; on
    Colab a local folder, so they are not written to Drive), which is deleted once <name>_best/ is saved; a run cannot
    be resumed. Returns the history and leaves the best weights loaded.
    """
    from transformers import EarlyStoppingCallback, Trainer, TrainingArguments    # needs accelerate; sampling doesn't
    ckpt_dir = Path(ckpt_dir)
    run_dir = Path(run_root or ckpt_dir) / f"{name}_run"
    model.config.use_cache = False                     # needed with gradient checkpointing
    args = TrainingArguments(
        output_dir=str(run_dir), num_train_epochs=epochs, learning_rate=lr,
        per_device_train_batch_size=batch_size, per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=accum, max_grad_norm=1.0, eval_strategy="epoch", save_strategy="epoch",
        save_only_model=True, load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
        save_total_limit=2, logging_strategy="epoch", report_to="none", seed=seed, data_seed=seed,
        fp16=torch.cuda.is_available(), gradient_checkpointing=gradient_checkpointing, remove_unused_columns=False)
    trainer = Trainer(model=model, args=args, train_dataset=train_ex, eval_dataset=val_ex,
                      data_collator=make_collate(tok.pad_token_id), processing_class=tok,
                      callbacks=[EarlyStoppingCallback(early_stopping_patience=patience)])
    trainer.train()
    model.config.use_cache = True
    best_dir = ckpt_dir / f"{name}_best"
    trainer.save_model(str(best_dir))
    tok.save_pretrained(str(best_dir))
    shutil.rmtree(run_dir, ignore_errors=True)
    history = epoch_history(trainer.state.log_history)
    json.dump(history, open(ckpt_dir / f"{name}_history.json", "w"), indent=2)
    best = min(r["val_loss"] for r in history)
    log(f"{name}: best val loss {best:.4f} (ppl {math.exp(best):.2f}), saved {best_dir}")
    return history


class AnswerRepetitionPenalty(LogitsProcessor):
    """System D's repetition penalty (qwen_lora.py): word tokens already in the poem are penalized. The prompt is left
    out (it lists the end words), and so are the end words, which each appear twice (tag and line end)."""

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
             max_new_tokens=128, device="cpu"):
    """Samples n poems in one batch, with the shared decoding settings. intensity is "mild" or "harsh" for a diss
    ("none" asks for a Stage 1 quatrain). Each result has its lines (tags stripped, at most four), the number of
    non-empty lines the model wrote, and the raw text."""
    model.eval()
    prompt = torch.tensor([tok.encode(prompt_text(list(traits), intensity, list(end_words)),
                                      add_special_tokens=False)], device=device)
    penalty = AnswerRepetitionPenalty(penalized_tokens(tok, model.config.vocab_size, end_words, device),
                                      prompt.shape[1], rep_penalty)
    out = model.generate(input_ids=prompt, attention_mask=torch.ones_like(prompt), do_sample=True,
                         temperature=temperature, top_p=top_p, top_k=0, repetition_penalty=1.0,
                         num_return_sequences=n, max_new_tokens=max_new_tokens, pad_token_id=tok.pad_token_id,
                         logits_processor=LogitsProcessorList([penalty]))
    texts = tok.batch_decode(out[:, prompt.shape[1]:], skip_special_tokens=True)
    return [{"lines": decode_lines(t), "line_count": sum(bool(l.strip()) for l in t.split("\n")), "text": t}
            for t in texts]
