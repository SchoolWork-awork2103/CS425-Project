# System E results (GPT-2 small + full fine-tune)

One training run of `generation/train_gpt2.ipynb` per checkpoint. The models themselves are in the shared Drive folder
(`MyDrive/CS425/checkpoints/gen_E_*_best/`); this folder keeps the numbers.

| Run | File | Base checkpoint |
|---|---|---|
| E-poems | `gen_E_poems_summary.json` | `ismaelfaro/gpt2-poems.en` (Kaggle poems) |
| E-crpo | `gen_E_crpo_summary.json` | `andreipb/gpt2-poetry-model-crpo` (Gutenberg Poetry Corpus) |

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
