"""Generate and save poems from base or fine-tuned checkpoint for rhyme evaluation."""
import argparse
import json
from pathlib import Path


def make_prompt(topic, tone, voice):
    return (f'Topic: {topic}\nTone: {tone}\nVoice: {voice}\n'
            'Write a four-line poem with an AABB rhyme scheme.\nPoem:\n')


def run(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = tokenizer.pad_token_id
    device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
    model.to(device).eval()
    prompt = make_prompt(args.topic, args.tone, args.voice)
    inputs = tokenizer(prompt, return_tensors='pt').to(device)
    with torch.inference_mode():
        sequences = model.generate(
            **inputs, max_new_tokens=args.max_new_tokens,
            do_sample=True, temperature=0.8, top_p=0.9, repetition_penalty=1.1,
            num_return_sequences=args.num_samples,
            pad_token_id=tokenizer.pad_token_id,
        )
    rows = []
    for i, seq in enumerate(sequences):
        new_ids = seq[inputs['input_ids'].shape[1]:]
        text = tokenizer.decode(new_ids, skip_special_tokens=True)
        # Assessment only: truncating lines doesn't guarantee the underlying poem is AABB.
        lines = [s.strip() for s in text.splitlines() if s.strip()]
        poem = '\n'.join(lines[:4])
        rows.append({'sample': i, 'model': args.model, 'topic': args.topic,
                     'tone': args.tone, 'voice': args.voice, 'poem': poem,
                     'generated_line_count': len(lines)})
        print(f'\n--- Sample {i+1} ---\n{poem}')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    print('Saved:', args.out)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--model', default='ismaelfaro/gpt2-poems.en')
    p.add_argument('--topic', default='procrastinating on homework')
    p.add_argument('--tone', default='sarcastic')
    p.add_argument('--voice', default='second person (you)')
    p.add_argument('--num-samples', type=int, default=5)
    p.add_argument('--max-new-tokens', type=int, default=128)
    p.add_argument('--out', type=Path, default=Path('runs/generated.jsonl'))
    run(p.parse_args())
