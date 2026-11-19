# Four-line roast chatbot

A local chatbot: tell it traits you're proud of, and it roasts you in an AABB quatrain. Each message goes through the NLU (DistilBERT intent and trait tagger), a rule-based dialogue manager, the rhyme planner, a generator (System A, the GRU; System D, Qwen2.5-1.5B + LoRA; or System E, GPT-2 small) and the reranker. Nothing calls an API at run time.

The design and results are in [pipeline.md](pipeline.md) (the evaluation results, also summarised below, in Phase 9); [ARCHITECTURE.md](ARCHITECTURE.md) maps it to the code and lists what is left.

## Setup

Python 3.10–3.13 (tested on 3.13), from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For System D on the GPU, install a CUDA build of PyTorch first ([PyTorch's installer](https://pytorch.org/get-started/locally/)).

Then download everything the app needs and check that it is in place:

```powershell
python -m app.setup_assets --download
python -m app.setup_assets
```

`--download` fetches the trained models from the team's Hugging Face repo (`paths.checkpoints_repo` in `config.yaml`) into `checkpoints/`, skipping any already there, so local copies are never replaced:

```text
checkpoints/
  nlu_joint_best/            # NLU (Phase 6)
  trait_fit_best/            # reranker trait-fit classifier (Phase 5)
  gen_A_rev_stage2_best.pt   # System A
  gen_D_1.5b_best/           # System D adapter
  gen_E_base_stage2_best/    # System E
```

It then fetches the public files: the Qwen2.5-1.5B-Instruct base (about 3 GB, which System D's adapter sits on), the MiniLM span encoder, the Detoxify checkpoint, BERT tokenizer files and the GloVe 6B archive, from which `data/glove/` is built.

The check exits nonzero if anything is missing, including the checkpoint of any of the three generators. If you already have `glove.6B.zip`, `python data/prepare_glove.py path/to/glove.6B.zip` builds `data/glove/` without the download.

## Run

```powershell
python -m app.chat --device cuda      # or --device cpu
```

System D is the default generator (`--system A` to start on the GRU, `--system E` on GPT-2 small); you can switch in the UI, and switching keeps the conversation's settings. Median time per turn, measured on one laptop, plugged in: System A 3.3 s on the CPU; System E 4.0 s and System D 13.2 s on the GPU. On the CPU alone E takes about 23 s and D is far slower, so without a GPU use A. A conversation to try:

1. `Roast me, I'm confident and musical`
2. `Another one, but harsher`
3. `Drop the musical part and add how organized I am`
4. `Roast my punctuality instead`
5. `reset`

Intensity starts at `mild` (the other value is `harsh`). A trait the NLU only guessed is used and named above the poem; one it can't place at all is asked about. `--backend qwen` swaps the NLU for System D's base model reading the message (slower, a comparison; pipeline.md, Phase 7).

## Configuration

`config.yaml`, under `dialogue`: the interpreter (`backend`), the default intensity, whether a reply must be full AABB (`require_aabb`; otherwise the best of any rhyme after one more batch), retries and history length. Reranker weights and filters are under `reranker`, decoding under `sampling`.

After changing `data/traits.json` or the diss training split, rebuild the trait catalogue (a test fails until you do):

```powershell
python -m dialogue.build_catalogue
```

## Tests and evaluation

```powershell
python -m unittest discover -v                                    # no models needed; planner tests skip without GloVe
python -m eval.run_dialogue_eval --mode policy                    # dialogue manager on the gold turns
python -m eval.run_dialogue_eval --mode interpreter               # + the real NLU (or --backend qwen --device cuda)
python -m eval.run_dialogue_eval --mode integrated --system A     # the whole pipeline (or --system D / E --device cuda)
```

The dialogue test set is `eval/dialogue_test.jsonl` (24 conversations, 61 turns; `eval/dialogue_dev.jsonl` for development). Results go to `eval/results/dialogue/`; the numbers are in pipeline.md, Phase 9.

### Automatic evaluation (the 50 frozen prompts)

```powershell
python -m eval.run_auto_eval generate --system E --device cuda                 # candidate pool with the planner's rhyme plans
python -m eval.run_auto_eval generate --system E --device cuda --plans random   # pool for the no-planner ablation
python -m eval.run_auto_eval analyse --device cuda                             # every pool -> summary.json, comparison.json
```

Run `generate` for each system (A on `--device cpu`); a run can be stopped and started again. It writes every candidate for the 50 prompts in `eval/prompts.json` (3 seeds), and `analyse` derives the configurations from them (the app as used, no reranker, 5 to 40 candidates, no planner, the generator alone). Results go to `eval/results/auto/`; the main table and the ablations are in pipeline.md, Phase 9.

### Human evaluation

```powershell
python -m eval.human_eval collect              # ratings -> eval/results/human/summary.json
```

The rating forms were built with `python -m eval.human_eval forms --raters 3` (a Google Apps Script and the poem key in `data/human_eval/`); that step is done and need not be run again.

Three raters outside the team (one who studied literature in upper secondary school and junior college, two who did not) rated 90 poems, blind and each in their own order: 30 of the 50 frozen prompts (all 5 held-out traits, 12 single-trait, 12 multi-trait, 1 with no trait), each answered by three configurations, from 1 to 5 on five criteria. The poems are the ones the automatic evaluation chose (seed 425):

- **D-full** and **E-full**: the app as used (rhyme planner, 20 candidates, reranker), with System D (Qwen2.5-1.5B + LoRA) or System E (GPT-2 small).
- **D-base**: System D alone, with random rhyme words, no reranker and only the toxicity filter.

Files: each rater's three Google Forms exports, one per part, as `data/human_eval/raw/human/evaluator<k>_0<p>.csv`; the same ratings in one CSV per rater, `data/human_eval/ratings/human/evaluator<k>.csv` (poem,coherence,relevance,humour,poetic,rhyme), which `collect` reads; the key (`items.jsonl`, which poem came from which configuration) in `data/human_eval/`.

**Results** (mean rating per configuration; each rater's scores averaged per poem):

| | Coherence | Relevance | Humour | Poetic quality | Rhyme |
|---|---|---|---|---|---|
| D-full | **2.41** | **3.26** | 2.07 | **2.51** | **4.13** |
| E-full | 1.70 | 2.71 | 1.62 | 2.09 | 3.93 |
| D-base | 2.27 | 3.11 | **2.12** | **2.51** | 3.86 |

- **People prefer D to E.** D-full is rated above E-full on coherence (+0.71), relevance (+0.54) and poetic quality (+0.42), and D-base above E-full on humour (+0.50) (paired Wilcoxon tests over the 30 prompts, Holm-adjusted p < 0.05). Each of the three raters ranks D-full above E-full on every criterion. The automatic metrics had D and E level on rhyme and on naming the traits; people find E's poems less coherent and less on topic.
- **People cannot tell D-full from D-base:** no criterion differs significantly. For System D, the rhyme planner and reranker do not measurably improve what a reader sees.
- **Humour is low for every configuration** (about 2 of 5), and nearly every poem rhymes, so rhyme ratings sit near the top for all three.
- **Agreement between raters is low** (Krippendorff's alpha, ordinal: 0.23 for coherence, −0.26 to −0.02 for the rest). Much of it is how they use the scale (one rater gave mostly 1s and 2s, another mostly 3s to 5s); on which poems are better they agree moderately on coherence (rank correlation 0.36 to 0.64 between pairs) and weakly on the rest. With 3 raters and 30 prompts the intervals are wide; the held-out traits are only 5 prompts.

**LLM judges** (a separate panel, not counted as raters): Claude, DeepSeek and Gemini rated the same 90 poems with the same guide (one CSV per model in `data/human_eval/ratings/llm/`, their original sheets in `data/human_eval/raw/llm/`). ChatGPT also rated them but is left out of the panel: it was the free base model, and it answered far faster than the others, so its ratings are likely less considered (its file is kept in `data/human_eval/ratings/excluded/`; including it does not change the conclusions). The three show the same pattern more strongly: D-full and D-base above E-full on coherence, relevance, humour and poetic quality (Holm-adjusted p ≤ 0.022), and D-full level with D-base. Their per-poem ratings agree with the human mean moderately (Spearman 0.52 to 0.75 for the three judges together on coherence, relevance, humour and poetic quality; Gemini the closest single judge) and weakly on rhyme (0.20). The full numbers, with intervals and every test, are in `eval/results/human/summary.json`.
