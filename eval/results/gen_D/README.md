# System D results (Qwen2.5-1.5B-Instruct + LoRA)

One training run of `generation/train_qwen.ipynb` on a Colab T4, 2026-10-28. The adapter itself is in the shared Drive
folder (`MyDrive/CS425/checkpoints/gen_D_1.5b_best/`); this folder keeps the numbers.

| File | Contents |
|---|---|
| `gen_D_1.5b_history.json` | train and val loss per epoch |
| `gen_D_1.5b_summary.json` | settings, history, test loss, sample checks for D, and the same checks for System A |

LoRA r=16, alpha=32, dropout 0.05 on q, k, v, o; lr 2e-4 with cosine schedule; 16 examples per step; 3 epochs on the
diss data, no Stage 1.

## Training

| Epoch | Train loss | Val loss | Val perplexity | Time |
|---|---|---|---|---|
| 1 | 1.778 | 1.561 | 4.76 | 283 s |
| 2 | 1.464 | 1.474 | 4.37 | 270 s |
| 3 | 1.368 | **1.463** | **4.32** | 270 s |

Best epoch is the last; val loss was still falling, but by only 0.01 in the last epoch.

| Diss test set | Loss | Perplexity |
|---|---|---|
| seen traits | 1.455 | 4.29 |
| held-out traits | 1.703 | 5.49 |

Perplexity is per Qwen token, so it is not comparable with System A's (different tokenizer).

## Samples: A and D on the same prompts

40 validation disses (training traits) and 40 held-out-trait disses from the test set, 4 samples each (160 per set),
temperature 0.8, top-p 0.9, repetition penalty 1.2. Each prompt uses the real diss's end words as the rhyme plan.
A is the final run (`gen_A_rev_stage2_best.pt`).

| | A seen | D seen | A held-out | D held-out |
|---|---|---|---|---|
| Exactly 4 lines | 100% | 100% | 100% | 100% |
| Lines ending on the planned rhyme word | 100% | 94% | 100% | 94% |
| Couplets that rhyme (CMUdict) | 100% | 89% | 100% | 89% |
| Full AABB | 100% | 81% | 100% | 79% |
| Mean `syllable_score` | 0.99 | 0.98 | 0.98 | 1.00 |
| Mean `lexical_score` | 0.99 | 1.00 | 0.99 | 0.99 |
| Mentions a listed trait or synonym | 64% | 78% | 0% | 69% |
| Distinct-2 | 0.55 | 0.66 | 0.51 | 0.62 |

A's trait mentions here (64%) differ from `gen_A/README.md` (71%) because the prompt sets are different.

## Takeaways

- D understands traits it never saw in training: held-out trait mentions go from 0% (A) to 69%, and its test loss on
  held-out traits is only 0.25 above seen traits. The base model already knows what "frugal" or "punctual" means.
- D is more varied than A (distinct-2 0.66 vs 0.55).
- D's form is weaker: lines are written forward and nothing forces the end word, so 6% of lines miss the planned word
  and about 1 in 5 poems is not full AABB, where A, which forces the rhyme word, reaches 100%. The reranker's
  `aabb_score` is what has to close this gap for D, by choosing among its candidates.
- D (1.5B) is meant to be the main generator; A is kept as the baseline.
