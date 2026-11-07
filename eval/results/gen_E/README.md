# System E results (GPT-2 small + full fine-tune)

One training run of `generation/train_gpt2.ipynb` per checkpoint. The models themselves are in the shared Drive folder

| Run | File | Base checkpoint |
|---|---|---|
| E-poems | `gen_E_poems_summary.json` | `ismaelfaro/gpt2-poems.en` (Kaggle poems) |
| E-crpo | `gen_E_crpo_summary.json` | `andreipb/gpt2-poetry-model-crpo` (Gutenberg Poetry Corpus) |
| E-base | `gen_E_base_summary.json` | `gpt2` (control: no poetry pretraining) |
| E-base, Stage 2 only | `gen_E_base_nos1_summary.json` | `gpt2`, trained on the disses only (ablation) |

Each summary holds the settings, the training history of both stages, test loss and sample checks.

Full fine-tune of all 124M parameters; lr 5e-5 (Stage 1) and 1e-5 (Stage 2); 16 examples per step; up to 5 epochs per
stage, early stopping with patience 2, keeping the epoch with the best val loss.

## E-poems (2026-11-01)

### Training

| Stage | Epoch | Train loss | Val loss | Val perplexity |
|---|---|---|---|---|
| 1 (quatrains) | 1 | 2.428 | 2.195 | 8.98 |
| | 2 | 2.078 | 2.124 | 8.36 |
| | 3 | 1.958 | 2.100 | 8.17 |
| | 4 | 1.881 | **2.097** | **8.14** |
| | 5 | 1.836 | 2.099 | 8.15 |
| 2 (disses) | 1 | 2.335 | 2.095 | 8.13 |
| | 2 | 2.102 | 2.003 | 7.41 |
| | 3 | 2.014 | 1.956 | 7.07 |
| | 4 | 1.968 | 1.931 | 6.90 |
| | 5 | 1.942 | **1.925** | **6.85** |

Stage 1 stopped improving after epoch 4, which is the one kept. Stage 2 was still improving at epoch 5 (the cap), but by
only 0.007. Stage 2 took about 12 minutes.

| Diss test set | Loss | Perplexity |
|---|---|---|
| seen traits | 1.929 | 6.88 |
| held-out traits | 2.090 | 8.09 |

Perplexity is per GPT-2 token, so it is comparable between E runs but not with System A or D (different tokenizers).

### Samples: A, D and E on the same prompts

The same prompts as `gen_D/README.md`: 40 validation disses (training traits) and 40 held-out-trait disses from the
test set, 4 samples each (160 per set), temperature 0.8, top-p 0.9, repetition penalty 1.2, the real diss's end words
as the rhyme plan. A and D are copied from `gen_D/gen_D_1.5b_summary.json`.

| | A seen | D seen | E seen | A held-out | D held-out | E held-out |
|---|---|---|---|---|---|---|
| Exactly 4 lines | 100% | 100% | 100% | 100% | 100% | 99% |
| Lines ending on the planned rhyme word | 100% | 94% | 89% | 100% | 94% | 94% |
| Couplets that rhyme (CMUdict) | 100% | 89% | 80% | 100% | 89% | 89% |
| Full AABB | 100% | 81% | 64% | 100% | 79% | 79% |
| Mean `syllable_score` | 0.99 | 0.98 | 0.98 | 0.98 | 1.00 | 0.99 |
| Mean `lexical_score` | 0.99 | 1.00 | 0.99 | 0.99 | 0.99 | 1.00 |
| Mentions a listed trait or synonym | 64% | 78% | 90% | 0% | 69% | 21% |
| Distinct-2 | 0.55 | 0.66 | 0.64 | 0.51 | 0.62 | 0.62 |

### Takeaways

- E learns the format fully: four lines, real words and diss-length lines, as well as A and D.
- E's rhyme is close to D's: full AABB 64% (seen) and 79% (held-out) against D's 81% and 79%. Like D, it writes lines
  forward and nothing forces the end word. With 40 prompts per set, the seen/held-out gap is likely noise from which
  rhyme words each set asks for, not a real difference.
- E names training traits more often than D (90% vs 78%), but rarely names held-out ones (21% vs 69%): GPT-2 small
  knows much less about words like "frugal" than Qwen 1.5B. It is still better than A (0%).
- Variety is close to D's (distinct-2 0.64 vs 0.66) and above A's.
- E-poems sits between A and D: D-like form from a model 12× smaller, but weak on unseen traits.

## E-crpo (2026-11-01)

Same settings and prompts as E-poems.

### Training

| Stage | Epoch | Train loss | Val loss | Val perplexity |
|---|---|---|---|---|
| 1 (quatrains) | 1 | 2.292 | 2.102 | 8.18 |
| | 2 | 1.991 | 2.041 | 7.70 |
| | 3 | 1.883 | 2.026 | 7.58 |
| | 4 | 1.813 | **2.021** | **7.54** |
| | 5 | 1.771 | 2.022 | 7.55 |
| 2 (disses) | 1 | 2.194 | 1.976 | 7.21 |
| | 2 | 1.984 | 1.893 | 6.64 |
| | 3 | 1.903 | 1.850 | 6.36 |
| | 4 | 1.860 | 1.827 | 6.22 |
| | 5 | 1.838 | **1.820** | **6.17** |

Same shape as E-poems: Stage 1 best at epoch 4, Stage 2 still improving at the cap by 0.007.

| Diss test set | Loss | Perplexity |
|---|---|---|
| seen traits | 1.821 | 6.18 |
| held-out traits | 2.001 | 7.40 |

### Samples: D, E-poems and E-crpo

| | D seen | E-poems seen | E-crpo seen | D held-out | E-poems held-out | E-crpo held-out |
|---|---|---|---|---|---|---|
| Exactly 4 lines | 100% | 100% | 100% | 100% | 99% | 100% |
| Lines ending on the planned rhyme word | 94% | 89% | 91% | 94% | 94% | 95% |
| Couplets that rhyme (CMUdict) | 89% | 80% | 83% | 89% | 89% | 91% |
| Full AABB | 81% | 64% | 71% | 79% | 79% | 84% |
| Mean `syllable_score` | 0.98 | 0.98 | 0.99 | 1.00 | 0.99 | 0.99 |
| Mean `lexical_score` | 1.00 | 0.99 | 0.99 | 0.99 | 1.00 | 0.99 |
| Mentions a listed trait or synonym | 78% | 90% | 88% | 69% | 21% | 39% |
| Distinct-2 | 0.66 | 0.64 | 0.61 | 0.62 | 0.62 | 0.61 |

### Takeaways

- E-crpo beats E-poems on every loss (val and test about 0.1 lower in both stages), so Gutenberg pretraining is the
  better starting point. Losses of the two are comparable: same tokenizer, same data.
- Rhyme improves: full AABB 64% → 71% (seen) and 79% → 84% (held-out). That is still 10 points below D on seen
  prompts, and level with D on held-out ones (84% vs 79% is within the noise of 40 prompts).
- Held-out trait mentions nearly double (21% → 39%) but stay well below D's 69%.
- Slightly less varied (distinct-2 0.61 vs 0.64).
- E-crpo is the stronger System E checkpoint so far.

## E-base (2026-11-01)

Same settings and prompts as E-poems; plain GPT-2 small, with no poetry pretraining, as the control.

### Training

| Stage | Epoch | Train loss | Val loss | Val perplexity |
|---|---|---|---|---|
| 1 (quatrains) | 1 | 2.246 | 2.080 | 8.00 |
| | 2 | 1.973 | 2.026 | 7.58 |
| | 3 | 1.863 | 2.011 | 7.47 |
| | 4 | 1.792 | **2.009** | **7.46** |
| | 5 | 1.750 | 2.011 | 7.47 |
| 2 (disses) | 1 | 2.150 | 1.929 | 6.88 |
| | 2 | 1.940 | 1.852 | 6.38 |
| | 3 | 1.864 | 1.812 | 6.12 |
| | 4 | 1.825 | 1.792 | 6.00 |
| | 5 | 1.803 | **1.786** | **5.97** |

Same shape as the other two: Stage 1 best at epoch 4, Stage 2 still improving at the cap by 0.006.

| Diss test set | Loss | Perplexity |
|---|---|---|
| seen traits | 1.785 | 5.96 |
| held-out traits | 1.970 | 7.17 |

### Samples: D and the three E checkpoints

| | D seen | E-poems seen | E-crpo seen | E-base seen | D held-out | E-poems held-out | E-crpo held-out | E-base held-out |
|---|---|---|---|---|---|---|---|---|
| Exactly 4 lines | 100% | 100% | 100% | 100% | 100% | 99% | 100% | 100% |
| Lines ending on the planned rhyme word | 94% | 89% | 91% | 91% | 94% | 94% | 95% | 95% |
| Couplets that rhyme (CMUdict) | 89% | 80% | 83% | 85% | 89% | 89% | 91% | 90% |
| Full AABB | 81% | 64% | 71% | 74% | 79% | 79% | 84% | 83% |
| Mean `syllable_score` | 0.98 | 0.98 | 0.99 | 0.98 | 1.00 | 0.99 | 0.99 | 0.99 |
| Mean `lexical_score` | 1.00 | 0.99 | 0.99 | 1.00 | 0.99 | 1.00 | 0.99 | 0.99 |
| Mentions a listed trait or synonym | 78% | 90% | 88% | 88% | 69% | 21% | 39% | 39% |
| Distinct-2 | 0.66 | 0.64 | 0.61 | 0.63 | 0.62 | 0.62 | 0.61 | 0.63 |

### Takeaways

- The control has the lowest loss of the three at every point: Stage 2 val loss 1.786 against 1.820 (crpo) and 1.925
  (poems), and the same order on both test sets. It also starts lower (Stage 1 epoch 1 val loss 2.080 against 2.102 and
  2.195). The losses are directly comparable: same tokenizer, data and settings.
- In samples, E-base and E-crpo are level (AABB 74% vs 71% seen, 83% vs 84% held-out; held-out trait mentions 39% each),
  within the noise of 40 prompts; both are ahead of E-poems.
- So poetry pretraining does not help here, and the Kaggle-poems checkpoint hurts. A likely reason: the disses are
  modern, conversational English, closer to GPT-2's web text than to Gutenberg or Kaggle poetry, and fine-tuning on
  poetry may have worn away some of what plain GPT-2 knew. The quatrain and diss data (Stage 1 and 2) already teach the
  form.
- E-base is the best System E checkpoint on loss and level with E-crpo on samples. All three stay well below D on
  held-out traits (39% at best vs 69%).

## E-base, Stage 2 only (2026-11-01)

Ablation: plain GPT-2 trained on the disses only, skipping Stage 1 (quatrains). Same Stage 2 settings (lr 1e-5, up to 5
epochs) and prompts as the full runs.

### Training

| Epoch | Train loss | Val loss | Val perplexity |
|---|---|---|---|
| 1 | 2.771 | 2.174 | 8.79 |
| 2 | 2.212 | 2.028 | 7.60 |
| 3 | 2.087 | 1.969 | 7.16 |
| 4 | 2.027 | 1.941 | 6.97 |
| 5 | 1.997 | **1.933** | **6.91** |

| Diss test set | Loss | Perplexity |
|---|---|---|
| seen traits | 1.939 | 6.95 |
| held-out traits | 2.159 | 8.67 |

### Samples: E-base with and without Stage 1

| | Full seen | Stage 2 only seen | Full held-out | Stage 2 only held-out |
|---|---|---|---|---|
| Exactly 4 lines | 100% | 96% | 100% | 95% |
| Lines ending on the planned rhyme word | 91% | 50% | 95% | 54% |
| Couplets that rhyme (CMUdict) | 85% | 30% | 90% | 29% |
| Full AABB | 74% | 13% | 83% | 11% |
| Mean `syllable_score` | 0.98 | 0.86 | 0.99 | 0.85 |
| Mean `lexical_score` | 1.00 | 1.00 | 0.99 | 1.00 |
| Mentions a listed trait or synonym | 88% | 78% | 39% | 23% |
| Distinct-2 | 0.63 | 0.71 | 0.63 | 0.71 |

### Takeaways

- Stage 1 is what teaches the form. Without it, only half the lines end on the planned rhyme word and full AABB drops
  from 74-83% to 11-13%; line lengths and trait mentions get worse too. Val loss is 0.15 higher (1.933 vs 1.786).
- The higher distinct-2 (0.71) is not a gain: lines that ignore the rhyme plan and length limits are freer to vary.
- Caveat: Stage 2 keeps its lr of 1e-5, chosen for continuing from Stage 1. Starting from plain GPT-2 at that rate,
  5 epochs may undertrain (train loss starts at 2.77 and val loss is still falling at epoch 5), so part of the gap may
  be the learning rate rather than the missing quatrains. A Stage 2-only run at 5e-5 would separate the two. Even so,
  the 3,382 disses alone are unlikely to make up for 18,850 quatrains of rhyme-plan practice.

## In the app (2026-11-07)

E-base (`gen_E_base_stage2_best/`) is generator E in the chat app. On the integrated dialogue eval
(`python -m eval.run_dialogue_eval --mode integrated --system E --device cuda`, 24 conversations, 61 turns, 48 of them
roasts; results in `eval/results/dialogue/integrated_nlu_E.json`), next to D on the same laptop, plugged in:

| | E (GPU) | D (GPU) |
|---|---|---|
| Turns with the expected state | 36/61 | 36/61 |
| Roasts returned, out of 48 | 48, no errors | 48, no errors |
| Median time per turn (p95) | 4.0 s (5.6 s) | 13.2 s (21.3 s) |
| Median time per roast | 4.2 s | 13.7 s |
| Peak GPU memory | 1.9 GiB | 5.0 GiB |

- The turn scores are the same for every generator: they come from the NLU and the dialogue manager. What E changes is
  the speed: about 3 times faster than D on the GPU, with under 40% of its memory.
- Still to measure: E and D on the CPU alone, where E's size should matter most.
