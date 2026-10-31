"""System E: GPT-2 small (124M) checkpoints already fine-tuned on poetry, fully fine-tuned on the quatrains and then
the disses (pipeline_gpt2.md). The checkpoints are listed under gpt2.models in config.yaml.

An example is a prompt and a completion. The loss covers the completion only, and an example longer than max_len is
skipped rather than truncated, so the last couplet never loses its rhyme. Building the prompts from the shared
corpora (traits, intensity, end words, with end-word tags) is Phase 3 in pipeline_gpt2.md.

Training and sampling. load_base() loads a Hugging Face checkpoint or a saved <name>_best/ directory alike.
"""
import json, math
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


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
    """The Trainer's log -> one row per epoch, as in gen_D_*_history.json (train loss is the mean of the logged
    losses within the epoch)."""
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
          gradient_checkpointing=False, seed=42, log=print):
    """Full fine-tune, validating every epoch and stopping after `patience` epochs without improvement.

    Writes <name>_best/ (model and tokenizer, loadable with load_base) and <name>_history.json; the Trainer's own
    epoch checkpoints go to <name>_run/. Returns the history and leaves the best weights loaded.
    """
    from transformers import EarlyStoppingCallback, Trainer, TrainingArguments    # needs accelerate; sampling doesn't
    ckpt_dir = Path(ckpt_dir)
    model.config.use_cache = False                     # needed with gradient checkpointing
    args = TrainingArguments(
        output_dir=str(ckpt_dir / f"{name}_run"), num_train_epochs=epochs, learning_rate=lr,
        per_device_train_batch_size=batch_size, per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=accum, max_grad_norm=1.0, eval_strategy="epoch", save_strategy="epoch",
        load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False, save_total_limit=2,
        logging_steps=50, report_to="none", seed=seed, data_seed=seed, fp16=torch.cuda.is_available(),
        gradient_checkpointing=gradient_checkpointing, remove_unused_columns=False)
    trainer = Trainer(model=model, args=args, train_dataset=train_ex, eval_dataset=val_ex,
                      data_collator=make_collate(tok.pad_token_id), processing_class=tok,
                      callbacks=[EarlyStoppingCallback(early_stopping_patience=patience)])
    trainer.train()
    model.config.use_cache = True
    best_dir = ckpt_dir / f"{name}_best"
    trainer.save_model(str(best_dir))
    tok.save_pretrained(str(best_dir))
    history = epoch_history(trainer.state.log_history)
    json.dump(history, open(ckpt_dir / f"{name}_history.json", "w"), indent=2)
    best = min(r["val_loss"] for r in history)
    log(f"{name}: best val loss {best:.4f} (ppl {math.exp(best):.2f}), saved {best_dir}")
    return history


@torch.no_grad()
def generate(model, tok, prompt, n=5, temperature=0.8, top_p=0.9, rep_penalty=1.1, max_new_tokens=128,
             device="cpu"):
    """Samples n completions in one batch. Each result has its first four non-empty lines and the number of lines
    the model wrote. Hugging Face's repetition penalty also covers the prompt; Phase 3 replaces it with System D's
    AnswerRepetitionPenalty."""
    model.eval()
    inputs = tok(prompt, return_tensors="pt").to(device)
    out = model.generate(**inputs, do_sample=True, temperature=temperature, top_p=top_p,
                         repetition_penalty=rep_penalty, num_return_sequences=n, max_new_tokens=max_new_tokens,
                         pad_token_id=tok.pad_token_id)
    texts = tok.batch_decode(out[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    results = []
    for t in texts:
        lines = [l.strip() for l in t.splitlines() if l.strip()]
        results.append({"lines": lines[:4], "line_count": len(lines), "text": t})
    return results
