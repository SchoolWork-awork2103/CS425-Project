# CS425 — AABB Poetry GPT-2 Baseline (Reproducible Starter)

## Status and provenance

- Source: teammate-provided `quatrains.jsonl` (20,000 synthetic poems; `model` metadata says Qwen/Qwen3-32B-FP8).
- **Data auditing and topic-disjoint splitting were executed locally.** See `data/audit_report.json`.
- **The fine-tuning script and generation script have NOT been run on a GPU in this package.** No trained checkpoint or outcome claim is included.
- This collection is mostly **general poetry**, not a labelled trait-to-diss dataset. It can support poetry-format training, but the final diss project needs trait-conditioned roast examples.
- Confirm the team has permission to use the synthetic training outputs, and record the generating model, prompts, and terms in the report.

## Why this is useful

A runnable baseline to compare a GPT-2 poetry checkpoint before and after fine-tuning on four-line AABB poems. Separate topics between train/validation/test to reduce trivial topic memorisation. The model is conditioned on `Topic`, `Tone`, and `Voice`. This is a **poetry** baseline, not yet a diss generator.

## Quickstart (Google Colab with GPU suggested)

1. Upload this project ZIP to Colab, extract it and open a terminal in the project directory. Or clone the files locally. Install:

```bash
pip install -r requirements.txt
```

2. `data/` contains prepared `train.jsonl`, `validation.jsonl`, `test.jsonl` and the audit report. To reproduce from the original file:

```bash
python scripts/prepare_data.py --input quatrains.jsonl --out data --seed 42
```

3. **Smoke test** a short training run before attempting the full corpus:

```bash
python scripts/train_gpt2.py --data-dir data --output-dir runs/smoke --epochs 1 --max-train-examples 100 --max-val-examples 20
```

4. Full fine-tune of the first poetry checkpoint (requires downloading model weights and a GPU for practical speed):

```bash
python scripts/train_gpt2.py --model ismaelfaro/gpt2-poems.en --data-dir data --output-dir runs/ismaelfaro --epochs 2 --gradient-checkpointing
```

To test the second model instead:

```bash
python scripts/train_gpt2.py --model andreipb/gpt2-poetry-model-crpo --data-dir data --output-dir runs/andreipb --epochs 2 --gradient-checkpointing
```

5. Compare 5 examples from the original model vs the fine-tuned one, with *identical topic/tone/voice inputs*:

```bash
python scripts/generate.py --model ismaelfaro/gpt2-poems.en --topic 'procrastinating on homework' --out runs/before.jsonl
python scripts/generate.py --model runs/ismaelfaro/final_model --topic 'procrastinating on homework' --out runs/after.jsonl
python scripts/evaluate_generations.py --input runs/before.jsonl
python scripts/evaluate_generations.py --input runs/after.jsonl
```

The generator samples stochastically, so a serious comparison needs more examples and multiple random seeds. Five examples are only a functional test. Prefer at least 50–100 matched topics for evaluation, plus human judgments of relevance/coherence/humour.

## What the training script does

- Downloads an existing GPT-2 poetry checkpoint from Hugging Face.
- Reads `prompt` and `completion` from the split JSONL files.
- Tokenises the topic/tone/voice instructions and poem separately.
- **Masks prompt tokens with `-100`** so the language-model loss is calculated on the target poem tokens only.
- Pads input IDs and attention masks; doesn't treat padding as a poem target.
- Skips rather than truncates poems longer than `--max-length` (default 256 tokens).
- Trains with validation each epoch, saves the best checkpoint, outputs `runs/.../final_model/`.

## Interpretation and limits

- CMUdict-based evaluation checks end-word phonetic rhyme. It is not a perfect rhyme/quality judge (accent/pronunciation variants and out-of-vocabulary words matter).
- AABB form does **not** guarantee coherent poems or humorous disses.
- A 20,000-poem synthetic dataset can teach format and style, but user-trait-to-insult conditioning requires another fine-tuning stage with inputs such as `Traits: lazy, overconfident` mapped to supervised diss-quatrain targets.
- The `score` field in the source contains only 4 and 5; it is generator-provided metadata, not an independent quality assessment.
- GPT-2 is not instruction tuned. It might require significant fine-tuning to use `Topic` / `Tone` / `Voice` prompts reliably.
- The README commands need internet access to download pretrained models and dependencies; model training was not run in this packaging environment.

## Suggested team responsibilities / next steps

1. Share this baseline and audit with the data creator; agree on a common frozen train/test split.
2. Run smoke-test training, fix environment-specific issues if any, and publish epoch loss + samples.
3. Run matched base-versus-fine-tuned samples, evaluate AABB/format and have teammates rate quality.
4. Request or create a smaller **trait-to-diss** supervised dataset for Stage 2; keep those examples separate from validation/test.
5. Compare against the GRU and Qwen baselines using the same prompts and human evaluation rubric.
