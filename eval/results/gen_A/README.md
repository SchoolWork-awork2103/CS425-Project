# System A results (GRU language model)

Two training runs of `generation/train_gru.ipynb` on a Colab T4, 2026-10-28. The checkpoints themselves are in the
shared Drive folder (`MyDrive/CS425/checkpoints`); this folder keeps the numbers.

| Run | Files | Line format |
|---|---|---|
| Baseline | `gen_A_summary.json`, `gen_A_stage{1,2}_history.json` | forward lines; rhyme words only in the prefix |
| Final | `gen_A_rev_summary.json`, `gen_A_rev_stage{1,2}_history.json` | word-reversed lines; each line's rhyme word forced at decoding |

Both use the same model: 300-dim embeddings, 2-layer GRU with 512 hidden units, dropout 0.3, 9.3M parameters.

## Training

| | Baseline | Final |
|---|---|---|
| Stage 1 (quatrains): epochs / best val perplexity | 29 / 34.7 | 40 / 32.6 |
| Stage 2 (disses): epochs / best val perplexity | 30 (hit the cap) / 15.9 | 49 (early stop) / 15.1 |
| Diss test perplexity, seen traits | 15.6 | 15.0 |
| Diss test perplexity, held-out traits | 40.9 | 40.5 |

## Form, on validation-diss prompts (160 samples each)

| | Baseline | Final |
|---|---|---|
| Exactly 4 lines | 100% | 100% |
| Lines ending on the planned rhyme word | 27% | 100% |
| Couplets that rhyme (CMUdict) | 31% | 100% |
| Full AABB | 6% | 100% |

## Other checks (40 validation prompts and 20 held-out-trait prompts, 4 samples each)

| | Baseline | Final |
|---|---|---|
| Mentions a listed trait or synonym (seen traits) | 71% | 71% |
| Mentions a listed trait or synonym (held-out traits) | 0% | 0% |
| Non-words | 0.7% | 0.5% |
| 4-grams also in the training disses (real validation disses: 22%) | 28% | 23% |
| Distinct-2 | 0.57 | 0.56 |

## Takeaways

- Forcing each line's rhyme word fixes the form (full AABB 6% → 100%) at no cost to trait mentions, vocabulary,
  originality or diversity.
- Lines are roast-shaped but often ungrammatical or meaningless, in both runs: the limit of a 9M-parameter GRU
  trained from scratch on under a million tokens. Lines sometimes pad towards a hard rhyme word
  ("from the same old bean and bean") and slip out of the second person ("all i do is ...").
- Held-out traits are never mentioned: the model does not know what an unseen trait means. The rhyme plan still
  carries some meaning ("frugal" with coin / join / dime / time produced lines about coins and wallets), which
  supports choosing rhyme words that are semantically close to the trait.
- System A is kept as the baseline; System D (Qwen2.5-0.5B + LoRA) is meant to be the generator that makes sense.
