# Overview

**What this is:** the plan for **System E**, a GPT-2 small (124M) generator that starts from a checkpoint already
fine-tuned on poetry.

**Why it is worth building:**
- **Size axis.** A is a 9.3M GRU trained from scratch and D is a 1.5B instruction model. E (124M, pretrained) sits
  between them, so the report can show how rhyme control, trait relevance and fluency change with model size and
  pretraining.
- **Poetry pretraining as a controlled comparison.** The two candidate checkpoints share the GPT-2 small architecture
  and tokenizer and differ only in their poetry data. Adding plain `gpt2` as a control isolates what poetry
  pretraining adds:

  | ID | Checkpoint | Pretrained on |
  |---|---|---|
  | E-poems | `ismaelfaro/gpt2-poems.en` | Kaggle poems dataset (mostly modern) |
  | E-crpo | `andreipb/gpt2-poetry-model-crpo` | Gutenberg Poetry Corpus (old verse; the corpus Phase 1a rejected), 3 epochs |
  | E-base | `gpt2` [Recommended] | no poetry (control) |

  All three use the same tokenizer, so their perplexities **can** be compared with each other (not with A or D).
- **Cheap.** A full fine-tune of 124M fits a small consumer GPU or a Colab T4, and it runs on a CPU much faster than
  D, which matters for the demo.

**Systems to compare:** add a row to the table in `pipeline.md`:

| ID | Generator | Course link | Priority |
|---|---|---|---|
| E | GPT-2 small (124M), poetry-pretrained, full fine-tune | Week 6 | Optional |

**Priority tags** as in `pipeline.md`: **[Core]**, **[Recommended]**, **[Optional]**.

---

# Phase 0: Setup

Done. What changed:

| File | Change |
|---|---|
| `generation/gpt2_lm.py` | Added: loading, training and sampling for E, moved from the GPT-2 poetry baseline |
| `generation/test_gpt2_lm.py` | Added: unit tests for `gpt2_lm.py` and the data splits E uses |
| `config.yaml` | Added the `gpt2:` section: checkpoints, checkpoint names and training settings |
| `requirements.txt` | Added `accelerate`, needed for training |
| `cs425_poetry_baseline/` | Deleted |

Tests: `python -m unittest generation.test_gpt2_lm -v` from the project root (6 pass).

---

# Phase 1: Data

No changes.

---

# Phase 2: Phonetic module

No changes.

---

# Phase 3: Generators

### Shared settings
No changes to the BPE tokenizer: it is for the from-scratch systems, and E keeps GPT-2's own tokenizer.

### System E: GPT-2 small, poetry-pretrained [Optional]

**Prompt format and data loading: done.** What changed in `generation/gpt2_lm.py`:

| Change | Detail |
|---|---|
| Added `prompt_text()`, `answer_text()`, `decode_lines()` | The prompt and tagged poem below; `decode_lines` strips the tags and keeps the first four lines |
| Added `load_split(stage, split)` | (prompt, poem) pairs: Stage 1 from `data/quatrains/corpus/quatrains_{train,val}.jsonl` (18,850 / 1,000), Stage 2 from `data/disses/corpus/{train,val,test}.jsonl` (3,382 / 423 / 569) |
| Changed `generate()` | Takes traits, intensity and end words instead of a prompt string, and strips the tags. Uses System D's repetition penalty instead of Hugging Face's, and `top_k=0` so only top-p applies, as in D |

```
Traits: romantic, wise
Intensity: mild
Rhymes: heart apart insight blight
Poem:
[heart] you say you fill life with romance and keep love near the heart,
[apart] but your cliches are so thick, they drive true feelings far apart.
[insight] you claim your wisdom adds depth and gives us fresh insight,
[blight] when it's just a stream of platitudes that chokes the conversation's blight.<|endoftext|>
```

- Stage 1 quatrains have `Traits: none` and `Intensity: none`, as in System A. Fallback disses have `Traits: none`
  with `mild` or `harsh`, so the two stay apart. Topic, tone and voice are dropped.
- **Why the penalty changed:** the prompt's `Rhymes:` line contains the same tokens the lines must end on
  (` heart`), and Hugging Face's penalty also covers the prompt, so it pushed the model away from the planned end
  words. D's penalty (copied from `qwen_lora.py`, which needs `peft` to import) leaves out the prompt and the end
  words.
- **Checked** on all 24,224 poems: each end word is its line's last word; every poem has 4 lowercase ASCII lines with
  no brackets; encoding prompt and poem separately gives the same tokens as encoding them together; the longest
  example is 118 GPT-2 tokens (none skipped at `max_len` 256) and the longest poem 93 (within `max_new_tokens` 128).
  All three checkpoints have the same vocabulary and merges.
- **Tested:** 11 unit tests pass. A forward pass and `generate()` ran on a tiny random GPT-2.

**Smoke test: done** on a local GPU, with torch 2.14.1 and transformers 5.22.1. E-poems, Stage 1 on 100 quatrains
(1 epoch), then Stage 2 from Stage 1's best weights on 100 disses (3 epochs), 20 validation examples each, settings
from `config.yaml`; then reloaded from `_best/` and sampled.

| Stage | Val loss per epoch | Peak GPU memory |
|---|---|---|
| 1 | 4.67 | 3.07 GiB |
| 2 | 4.61, 4.45, 4.40 | 3.28 GiB |

What changed in `generation/gpt2_lm.py` after the first smoke run:

| Change | Why |
|---|---|
| `train()` logs once per epoch (`logging_strategy="epoch"`) | Logging every 50 steps left `train_loss` empty on short runs and misaligned with epochs on long ones |
| `train()` saves model-only checkpoints and deletes `<name>_run/` after saving `<name>_best/` | Each checkpoint held the optimizer state (1.4 GB; 2.8 GB per run) that nothing used, since a run cannot be resumed. A finished run now takes 0.5 GB |

`config.yaml`: the `accum` comment now gives batch 8's peak memory (it said to use batch 4 × 4 on a small GPU).

- The rerun gave the same losses and samples as the first run, so runs are reproducible with the seed.
- Samples after 7 training steps are not yet poems (one long line, tags in the middle), as expected. Two habits of
  the E-poems checkpoint to check after full training: it writes a literal `\n` (backslash, n) as a line break, and
  capital letters, where the training data is lowercase with real line breaks.

Still to do:

1. **Reversed lines** like System A [Optional ablation]: they force every end word, but reversed text wastes GPT-2's
   English pretraining, so expect worse fluency.
2. **E-crpo quirk:** that checkpoint expects `<start>` at the start of every line. Fine-tuning teaches the new format,
   but check the first Stage 1 samples for leftover `<start>` tags.
3. **Training** (full fine-tune, AdamW, fp16, gradient clipping at 1.0):
   - Stage 1 on quatrains: lr 5e-5, up to 5 epochs, early stopping (patience 2), keep the best val loss.
   - Stage 2 on disses: lr 1e-5 (about 1/5 of Stage 1, as for A), up to 5 epochs, same stopping rule.
   - 16 examples per step (batch 8 × 2 accumulation).
4. **Runs:**

   | Run | Priority | Notes |
   |---|---|---|
   | E-poems, Stage 1 + 2 | Core for E | |
   | E-crpo, Stage 1 + 2 | Core for E | the two-model comparison the baseline was made for |
   | E-base, Stage 1 + 2 | Recommended | control: no poetry pretraining |
   | best of the above, Stage 2 only | Recommended | ablation: does Stage 1 still help a pretrained model? |
   | best, reversed lines | Optional | ablation: end-word tags against forced end words |

   - Log train loss, val loss and perplexity per epoch. Save `eval/results/gen_E/gen_E_<run>_history.json` and
     `_summary.json`, in the same format as `gen_D`.
5. **Notebook: done.** Added `generation/train_gpt2.ipynb`, built like `train_qwen.ipynb`: clones the repo and mounts
   Drive in Colab, picks the checkpoint (`MODEL_KEY`) and whether to run Stage 1 (`STAGE1`), skips a stage that has
   already finished, samples the same 40 + 40 prompts as D and scores them with D's `report()`, counts leftover
   checkpoint habits (`<start>`, literal `\n`, capitals), computes test loss, compares with A and D from D's saved
   results, and saves `<name>_summary.json`. `train()` gained `run_root`, so on Colab the epoch checkpoints stay off
   Drive. All code cells ran in smoke-test mode (`SMOKE_TEST=1`).

### Decoding, for all systems
No changes to the settings. For E, the repetition penalty is done (above). Still to do:
- Stop after the fourth line or at `<eos>`. Now generation runs to `<eos>` or 128 tokens and the first four lines are
  kept.
- Return each candidate's length-normalized log-probability, which the reranker needs.

---

# Phase 4: Retrieval

No changes.

---

# Phase 5: Reranker

E's candidates go through the same hard filters and combined score. The weights are tuned on A and D candidates, so
check whether E's log-probability range needs its own scaling (it is already scaled within each prompt).

---

# Phase 6: NLU

No changes.

---

# Phase 7: Dialogue manager

No changes.

---

# Phase 8: Integration

1. Add E to the generator dropdown in the Gradio UI.
2. Measure E's response time on CPU next to the other systems.

---

# Phase 9: Evaluation

1. **Sample checks** on the same prompts as the System D notebook (40 validation disses + 40 held-out-trait test
   disses, 4 samples each, real end words as the rhyme plan), with the same metrics: exactly 4 lines, end-word hit,
   couplets rhyme, full AABB, `syllable_score`, `lexical_score`, trait mention, distinct-2. Move `report()` out of
   `qwen_lora.py` into a shared module so A, D and E all use the same code.
2. **Test loss**, seen and held-out traits apart. It is comparable across E-poems, E-crpo and E-base only.
3. **The 50 frozen prompts** (`eval/prompts.json`), through the rhyme planner, as for every other system. The planner
   needs the GloVe files, which are git-ignored: build them with `python data/prepare_glove.py`.
4. **Ablations:** add E's rows to the main table: with and without Stage 1, rhyme planning and reranking.
5. **Human evaluation** [Optional]: only if one E variant clearly beats A, swap it in as a configuration.
6. Write `eval/results/gen_E/README.md` with the tables and takeaways, matching `gen_D/README.md`.

**What to look for:** whether poetry pretraining improves rhyme and form (E-poems / E-crpo against E-base), whether
Gutenberg pretraining makes the language more archaic (E-crpo), and where E lands between A and D on trait mentions
for held-out traits.

---

# Phase 10: Report and demo

- Describe E as the mid-size pretrained transformer and state the poetry-pretraining comparison as a contribution.
- Record both checkpoints' sources and licenses (both MIT on Hugging Face) and what they were trained on.
- Error analysis: archaic vocabulary from E-crpo, missed end words, lines that drift off-trait.
- Notes from the GPT-2 poetry baseline's README, for the limitations section:
  - GPT-2 is not instruction-tuned, so it learns the prompt format only from fine-tuning.
  - The quatrains' `score` field (4 or 5 only) is the generating model's own judgment, not an independent quality
    rating.
  - The CMUdict rhyme check misses pronunciation variants and unknown words, and AABB form says nothing about
    coherence or humour.
  - Sampling is random: compare systems on many prompts and more than one seed, with human ratings.
- No changes to the demo.

---

# Timeline

Order of work for E:

| Step | Work | Depends on |
|---|---|---|
| 1 | Move the baseline code into `generation/gpt2_lm.py`, delete `cs425_poetry_baseline/` (done) | none |
| 2 | Prompt format with end-word tags, data loading from the shared corpora, unit tests (done) | 1 |
| 3 | Smoke test locally (done) | 2 |
| 4 | `train_gpt2.ipynb` (done), full runs E-poems and E-crpo (then E-base) | 3 |
| 5 | Sample checks, `gen_E` results README | 4 |
| 6 | Frozen prompts, reranker and app hookup | 5 and the team's Phase 5/8 code |

# Risks and fallbacks

Added for E:
- **AABB is poor with forward lines** (the forward GRU reached only 6% full AABB): rely on the end-word tags plus the
  reranker's `aabb_score`. If the tags aren't enough, try the reversed-lines run.
- **E-crpo writes archaic verse even after fine-tuning:** report it as a finding. It supports Phase 1a's decision to
  drop Gutenberg.
- **A local GPU is too slow:** run on a Colab T4. Memory is not the limit: batch 8 peaks at 3.3 GiB.
- **Short on time:** E-poems only, Stage 1 + 2, sample checks. Drop E-base and the ablations.
