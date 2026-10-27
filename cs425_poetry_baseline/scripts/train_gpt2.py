"""Conditionally fine-tune a GPT-2 poetry checkpoint; loss on the poem, not prompt."""
import argparse
import json
from pathlib import Path


def load_rows(path, limit):
    with path.open(encoding='utf-8') as f:
        rows = [json.loads(line) for line in f if line.strip()]
    if limit:
        rows = rows[:limit]
    return rows


class PoemDataset:
    def __init__(self, rows, tokenizer, max_length):
        self.examples = []
        self.skipped = 0
        for row in rows:
            prompt_ids = tokenizer.encode(row['prompt'], add_special_tokens=False)
            poem_ids = tokenizer.encode(row['completion'], add_special_tokens=False) + [tokenizer.eos_token_id]
            if len(prompt_ids) + len(poem_ids) > max_length:
                self.skipped += 1
                continue  # Do not truncate the last couplet or break the rhyme scheme.
            self.examples.append({
                'input_ids': prompt_ids + poem_ids,
                'attention_mask': [1] * (len(prompt_ids) + len(poem_ids)),
                'labels': [-100] * len(prompt_ids) + poem_ids,
            })
        if not self.examples:
            raise ValueError('No examples fit max_length. Try a larger --max-length.')

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx]


class PadCollator:
    def __init__(self, tokenizer):
        self.pad_id = tokenizer.pad_token_id

    def __call__(self, examples):
        import torch
        length = max(len(x['input_ids']) for x in examples)
        data = {}
        for key, pad_value in [('input_ids', self.pad_id),
                               ('attention_mask', 0), ('labels', -100)]:
            data[key] = torch.tensor([
                e[key] + [pad_value] * (length - len(e[key])) for e in examples
            ], dtype=torch.long)
        return data


def run(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainingArguments

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.eos_token_id is None:
        raise ValueError('The pretrained tokenizer has no EOS token.')
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model)
    model.config.pad_token_id = tokenizer.pad_token_id
    model.config.use_cache = False  # Compatible with gradient checkpointing.

    train_rows = load_rows(args.data_dir / 'train.jsonl', args.max_train_examples)
    val_rows = load_rows(args.data_dir / 'validation.jsonl', args.max_val_examples)
    train_ds = PoemDataset(train_rows, tokenizer, args.max_length)
    val_ds = PoemDataset(val_rows, tokenizer, args.max_length)
    print(f'Using {len(train_ds)} train, {len(val_ds)} validation examples; '
          f'skipped train={train_ds.skipped}, val={val_ds.skipped} for length')

    kwargs = dict(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        eval_strategy='epoch',
        save_strategy='epoch',
        load_best_model_at_end=True,
        metric_for_best_model='eval_loss',
        greater_is_better=False,
        save_total_limit=2,
        logging_steps=50,
        report_to='none',
        seed=42,
        data_seed=42,
        fp16=torch.cuda.is_available(),
        gradient_checkpointing=args.gradient_checkpointing,
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=TrainingArguments(**kwargs),
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=PadCollator(tokenizer),
        processing_class=tokenizer,
    )
    trainer.train()
    results = trainer.evaluate()
    print('Final validation metrics:', results)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model.config.use_cache = True
    trainer.save_model(str(args.output_dir / 'final_model'))
    tokenizer.save_pretrained(str(args.output_dir / 'final_model'))
    (args.output_dir / 'validation_metrics.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model', default='ismaelfaro/gpt2-poems.en', help='Or andreipb/gpt2-poetry-model-crpo')
    p.add_argument('--data-dir', type=Path, default=Path('data'))
    p.add_argument('--output-dir', type=Path, default=Path('runs/gpt2_poems'))
    p.add_argument('--epochs', type=float, default=2)
    p.add_argument('--batch-size', type=int, default=2)
    p.add_argument('--gradient-accumulation', type=int, default=8)
    p.add_argument('--learning-rate', type=float, default=5e-5)
    p.add_argument('--max-length', type=int, default=256)
    p.add_argument('--max-train-examples', type=int, default=0, help='0 means full dataset')
    p.add_argument('--max-val-examples', type=int, default=0)
    p.add_argument('--gradient-checkpointing', action='store_true')
    run(p.parse_args())
