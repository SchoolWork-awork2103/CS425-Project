# Architecture and status

How the finished product is meant to fit together, and where each piece stands. The design is in [pipeline.md](pipeline.md); this file maps it to code. Status was checked against the repo on **2026-11-07** (branch `feat/dialogue-integration` at `d318b88`: `feat/phase0` with the dialogue manager from `feat/phase0-david` and System E from `feat/pretrained_poem_models` merged in).

**Legend:** ✅ done · 🟡 partly done · ⬜ not started · ➖ optional, not planned unless there is time

---

## 1. The product in one picture

A user chats with the bot, names traits they're proud of, and gets back an AABB quatrain that roasts them. Everything at run time is local (no API calls).

```mermaid
flowchart LR
    U([User message]) --> NLU
    subgraph RT[Run time: Pipeline.respond]
        NLU["NLU + keyword rules<br/>intent + TRAIT spans<br/>→ trait edits, intensity"] --> DM["Dialogue manager<br/>state: traits, intensity,<br/>history, last plan"]
        DM -->|generate| PL["Rhyme planner<br/>top 2 plans<br/>(4 end words each)"]
        PL --> RET["Retrieval (optional)<br/>BM25 top 3 disses"]
        PL --> GEN["Generator A, D or E<br/>10 samples × 2 plans<br/>≈ 20 candidates"]
        RET -. few-shot / extra candidates .-> GEN
        GEN --> RR["Reranker<br/>hard filters → instant scores<br/>→ trait-fit on top 5<br/>→ combined score"]
        RR --> DM2["Dialogue manager<br/>store poem in history"]
    end
    DM -->|ask for traits / redirect / bye| R([Reply])
    DM2 --> R
```

The same chain as text:

```
message ─► NLUInterpreter.interpret ─► DialogueManager.step ─┬─► (no generation) canned reply / question
                                                              └─► RhymePlanner.plan ─► generator ─► Reranker.rerank ─► reply
```

## 2. How the models are built (offline)

```mermaid
flowchart TB
    subgraph LLM["Qwen3-32B-FP8 on the L40 (vLLM), offline only"]
        Q1a[1a quatrain_gen.ipynb]
        Q1b[1b diss_gen.ipynb]
        Q1d[1d nlu_gen.ipynb]
        Q1e[1e negatives_gen.ipynb]
    end
    T[data/traits.json<br/>40 traits, 5 held out] --> Q1b & Q1d & Q1e
    CSV[diss_style_examples.csv] --> Q1b
    Q1a --> C1a[quatrain corpus<br/>18,850 / 1,000]
    Q1b --> C1b[diss corpus<br/>3,382 / 423 / 569]
    Q1d --> C1d[NLU corpus<br/>2,624 / 328 / 529]
    Q1e --> C1e[negatives<br/>2,235]
    C1a -->|off_topic| C1e
    C1b -->|wrong_trait| C1e

    C1a & C1b --> TOK[BPE 8k tokenizer]
    TOK --> A1[System A Stage 1<br/>quatrains] --> A2[System A Stage 2<br/>disses]
    C1b --> D[System D<br/>Qwen2.5-1.5B + LoRA]
    C1a & C1b --> E[System E<br/>GPT-2 small, full fine-tune]
    C1b & C1e --> TF[Trait-fit DistilBERT]
    C1d --> NLUM[Joint NLU DistilBERT]
    C1d --> NORM[Trait normalizer<br/>MiniLM kNN]
    GLOVE[GloVe 6B 300d] --> PLAN[Rhyme planner]
    PLAN & A2 & D --> POOL[Rating pool<br/>600 candidates → 150 rated]
    POOL --> W[Reranker weights<br/>grid search]
```

Phonetics (`phonetics/`, `data/form_checks.py`) sits under all of this: it filters every dataset, scores candidates in the reranker, and is the main metric in evaluation.

---

## 3. Components

| # | Component | Code | Inputs → outputs | Status |
|---|---|---|---|---|
| 0 | Config, seeds, paths | [config.yaml](config.yaml), [utils.py](utils.py) | | ✅ |
| 0 | Traits | [data/traits.json](data/traits.json) | 40 traits with `description`, `flip`, `synonyms`, `heldout` (eloquent, punctual, patient, worldly, frugal); [data/trait_catalogue.json](data/trait_catalogue.json) adds training counts (`python -m dialogue.build_catalogue`) | ✅ |
| 0 | Frozen eval prompts | [eval/prompts.json](eval/prompts.json) | 50 prompts (single / multi / held-out / unclear) | ✅ |
| 1a | Quatrain corpus | [data/quatrains/](data/quatrains/) | 20,000 generated → 18,850 train / 1,000 val (split by topic group) | ✅ |
| 1b | Diss corpus | [data/disses/](data/disses/) | 4,374 after filters → 3,382 / 423 / 569 (146 held-out in test) | ✅ (manual review skipped by design) |
| 1c | Rhyme-word annotation | in `prepare_*.py` | every diss/quatrain row has `end_words` and `rhymes` | ✅ |
| 1d | NLU data | [data/nlu/](data/nlu/) | 3,481 messages, 7 intents, BIO `TRAIT` | ✅ (spot check needs team confirmation) |
| 1e | Reranker negatives | [data/negatives/](data/negatives/) | 2,235 (flat, non_rhyming, off_topic, wrong_trait) | ✅ |
| 2 | Phonetic module | [phonetics/rhyme.py](phonetics/rhyme.py), [phonetics/scores.py](phonetics/scores.py) | `rhymes`, `aabb_score`, `syllable_score`, `lexical_score`, `form_scores` | ✅ (12 tests pass) |
| 2 | Rhyme planner | [phonetics/planner.py](phonetics/planner.py) | `plan_rhymes(traits, k, exclude)` → list of `[a1, a2, b1, b2]` | ✅ (fixed version, short common end words) |
| 3 | Tokenizer | [generation/tokenizer/](generation/tokenizer/) | sentencepiece BPE 8k with `<traits> <intensity> <rhymes> <poem> <nl>` | ✅ |
| 3 | System A: GRU LM | [generation/gru_lm.py](generation/gru_lm.py), [sequences.py](generation/sequences.py) | `generate(model, codec, traits, intensity, end_words, n)` | ✅ forward baseline + reversed-line final (`gen_A_rev_stage2_best.pt`) |
| 3 | System B: GRU enc-dec | | | ➖ not started |
| 3 | System C: small Transformer | | | ➖ not started |
| 3 | System D: Qwen2.5-1.5B + LoRA | [generation/qwen_lora.py](generation/qwen_lora.py) | `generate(model, tok, traits, intensity, end_words, n)`; `score(...)` for given poems | ✅ 1.5B (`gen_D_1.5b_best/`); penalty bug in log-probability fixed 2026-11-04; 0.5B / 3B size comparison ➖ |
| 3 | System E: GPT-2 small + full fine-tune | [generation/gpt2_lm.py](generation/gpt2_lm.py), [train_gpt2.ipynb](generation/train_gpt2.ipynb) | `generate(model, tok, traits, intensity, end_words, n)` | ✅ E-base (`gen_E_base_stage2_best/`); E-poems, E-crpo and Stage 2-only runs compared ([eval/results/gen_E/](eval/results/gen_E/)); 12 tests pass |
| 4 | Retrieval (BM25) | [retrieval/](retrieval/) (empty) | `retrieve(traits, k=3)` | ➖ not started |
| 5 | Trait-fit classifier | [reranker/trait_fit.py](reranker/trait_fit.py) | `TraitFit.score(traits, poems)` → probabilities | ✅ test AUC 0.984, held-out 0.966 |
| 5 | Combined reranker | [reranker/rerank.py](reranker/rerank.py) | `Reranker().rerank(traits, candidates, history)` → kept candidates, best first | ✅ (history repeat check added; 3 tests) |
| 5 | Weight tuning | [reranker/rating_pool.py](reranker/rating_pool.py), [tune_weights.py](reranker/tune_weights.py) | 150 rated candidates → weights | ✅ inconclusive, equal weights kept; rerun after D's log-probabilities were rescored (pipeline.md, Phase 5) |
| 6 | Joint NLU | [nlu/joint_model.py](nlu/joint_model.py) | `NLU.parse(text)` → intent, spans, traits | ✅ intent acc 0.938 |
| 6 | Trait normalizer | [nlu/normalize.py](nlu/normalize.py) | span → trait key / unknown + nearest | ✅ (weakest step: 0.44–0.49 strict on gold spans) |
| 7 | Dialogue manager | [dialogue/manager.py](dialogue/manager.py), [types.py](dialogue/types.py) | `step(turn, state)` → `Decision` + new state | ✅ (61/61 on the gold turns) |
| 7 | Interpreter | [dialogue/interpreter.py](dialogue/interpreter.py) | `NLUInterpreter` (default) or `QwenInterpreter` (comparison): message → validated turn | ✅ NLU 36/61 turns; Qwen ⬜ not measured on these fixtures |
| 8 | Pipeline + Gradio UI | [app/pipeline.py](app/pipeline.py), [app/chat.py](app/chat.py) | `Pipeline.respond(message, state, system)`, Gradio Blocks, A / D / E dropdown | ✅ A on CPU: 48/48 roasts, median 3.9 s; D on GPU and E ⬜ not run |
| 8 | Run script + README | [README.md](README.md), [app/setup_assets.py](app/setup_assets.py) | `python -m app.chat --device cuda` | ✅ |
| 9 | Automatic eval on 50 prompts | [eval/run_auto_eval.py](eval/run_auto_eval.py), [auto_metrics.py](eval/auto_metrics.py) | `generate` (candidate pool per system) → `analyse` → `eval/results/auto/summary.json`, `comparison.json`; also the planner, reranker and candidates ablations | ✅ A, D and E, 3 seeds (2026-11-08); results in pipeline.md, Phase 9 |
| 9 | Ablations | [eval/run_auto_eval.py](eval/run_auto_eval.py) | with/without Stage 1, planner, reranker, retrieval; quality vs. candidates | ✅ planner, reranker and 1/5/10/20/40 candidates for A, D and E on the frozen prompts; Stage 1 for E, forward vs. reversed for A; retrieval not built (no Stage 1 ablation for A) |
| 9 | Dialogue eval | [eval/run_dialogue_eval.py](eval/run_dialogue_eval.py), [eval/dialogue_test.jsonl](eval/dialogue_test.jsonl) | 24 conversations / 61 turns → `eval/results/dialogue/` | ✅ NLU with A, D and E (36/61 each; D and E on the GPU, E also on the CPU); Qwen interpreter 19/61, so the NLU stays the default (2026-11-09) |
| 9 | Human eval | [eval/human_eval.py](eval/human_eval.py), [data/human_eval/](data/human_eval/) | `forms` (Google Forms) → ratings → `collect` → `eval/results/human/summary.json` | ✅ 3 evaluators outside the team, 30 prompts × D-full, E-full, D-base (90 poems), plus 3 LLM judges (Claude, DeepSeek, Gemini; ChatGPT excluded) as a separate panel (2026-11-09); results in pipeline.md, Phase 9, and README.md |
| 10 | Report and demo | | | ⬜ |

Checkpoints in `checkpoints/` (git-ignored, mirrored to Drive): `gen_A_*`, `gen_A_rev_*`, `gen_D_1.5b_best/`, `gen_E_{poems|crpo|base}_stage{1|2}_best/` (the app loads `gen_E_base_stage2_best/`), `nlu_joint_best/`, `trait_fit_best/`. GloVe files are in `data/glove/` (git-ignored, built by `data/prepare_glove.py`).

---

## 4. Run-time flow in detail

What happens inside `Pipeline.respond(message, state)` ([app/pipeline.py](app/pipeline.py)). Design and results are in pipeline.md, Phases 7 and 8.

1. **Control** — exact commands skip the interpreter: "reset", "cancel" and numbered or yes answers to a pending question.
2. **Interpret** — `NLUInterpreter.interpret(message, state)` runs `NLU.parse` and the keyword rules: meaner/softer words before the intent head, missed trait words, remove / replace / generic cues, and a note for a trait guessed by similarity. The result is a `TurnInterpretation`, validated in `dialogue/types.py`. `dialogue.backend: qwen` swaps in `QwenInterpreter`.
3. **Dialogue manager** — `DialogueManager.step(turn, state)` applies the trait edits and intensity, and either replies (canned / settings), asks (`clarify`, stored in `state.awaiting`) or decides to `generate`.
4. **Rhyme planner** — `RhymePlanner.plan(traits, k=2, exclude=last_plan)`, falling back to any plan if the exclusion leaves none.
5. **Retrieval** ➖ — not built.
6. **Generator** — 10 samples per plan at temperature 0.8, top-p 0.9, repetition penalty 1.2, so 20 candidates, each with its length-normalized log-probability. A forces the end words (reversed lines); D and E write forward with end-word tags and nothing forces the end word, so their rhyme depends on the reranker. D runs in `app/model_service.py`, which shares one Qwen model with the Qwen interpreter; E loads on first use from `gpt2.checkpoint` in `config.yaml`.
7. **Reranker** — `Reranker.rerank(traits, candidates, history)`: hard filters (4 lines, Detoxify limits, lexical ≥ 0.8, no exact repeat of `history`), instant features plus the ROUGE-L history penalty, `TraitFit` on the top 5, equal weights.
8. **Reply** — the best full-AABB candidate (one more batch if none, then the best of any rhyme), with the guessed-trait note above it. Only that poem is added to `history`, and its plan becomes `last_plan`.

```python
pipeline = Pipeline(cfg, system="D", device="cuda")    # D is the default; models load on first use
reply, state = pipeline.respond("roast me, I'm confident", pipeline.manager.initial_state())
pipeline.last_trace                                    # stage, interpretation, candidates, survivors, timings
```

---

## 5. What's left, in order

The evaluation the report needs, now that the product runs end to end.

1. **Systems D and E in the chat**: done on the GPU (2026-11-07): the integrated dialogue eval gives all three systems the same 36/61, with a median of 3.3 s per turn for A (CPU), 4.0 s for E and 13.2 s for D (GPU, same laptop; pipeline.md, Phase 8). On the CPU alone, E takes 22.9 s per turn, and D was too slow to finish the 61 turns, so without a GPU A is the generator. Still to do: recording the GPU clock with GPU latencies (TODO in `eval/run_dialogue_eval.py`).
2. **Qwen interpreter** on the dialogue test set: done (2026-11-09). 19/61 turns against the NLU's 36/61, 2/24 conversations against 9/24, and 4.0 s per message on the GPU against 0.02 s: it asks clarifying questions on clear requests (16 times). It is better only on unknown traits (1 wrongly matched of 6, against the NLU's 6), the turns written for it. The NLU stays the default (pipeline.md, Phase 9).
3. **Automatic eval** on the 50 frozen prompts: done (2026-11-08, `eval/run_auto_eval.py`, 3 seeds). With the reranker all three return a full-AABB poem almost every time; D and E are level on form and trait mentions (86% and 87%), A trails at 67% and never names a held-out trait (pipeline.md, Phase 9).
4. **Ablations**: done for the planner, the reranker and 1/5/10/20/40 candidates (A, D, E) and Stage 1 (E). Still open: no Stage 1 for A.
5. **Human eval**: done (2026-11-09, `eval/human_eval.py`). Three evaluators outside the team rated 90 poems: 30 frozen prompts × D-full, E-full and D-base (3 configurations instead of the planned 4; E replaced A, which the automatic evaluation already separates clearly). People prefer D to E (D-full above E-full on coherence, relevance and poetic quality, Holm p ≤ 0.004) and cannot tell D-full from D-base; humour is low everywhere and agreement between evaluators is low (alpha −0.26 to 0.23). Claude, DeepSeek and Gemini rated the same poems as a separate LLM panel and show the same pattern; ChatGPT's ratings are excluded (free base model, answered far faster than the others) without changing that (pipeline.md, Phase 9).
6. **Report and demo.**

Before submission: the team confirms the NLU spot check (`data/nlu/corpus/spot_check.csv`, 348 rows marked by Claude only, 42 wrong).

`archive/` holds files the pipeline no longer uses: the cluster working copies and pilot runs of the LLM data generation (`disses/`, `negatives/`, `nlu/`, `quatrains/`) and, in `legacy/`, the first prototype from before this pipeline (`Datasets/` with the sonnets and the old diss CSV, and its Colab notebook `Train.ipynb`).

Optional, only if time allows: retrieval (Phase 4), Systems B and C, the D size comparison (0.5B / 3B), E with reversed lines or Stage 2 only at lr 5e-5 (neither is likely to change a conclusion), and a second round of reranker ratings once the poems are better.
