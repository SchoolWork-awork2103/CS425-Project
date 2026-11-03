# Four-line roast chatbot

A local chatbot: tell it traits you're proud of, and it roasts you in an AABB quatrain. Each message goes through the NLU (DistilBERT intent and trait tagger), a rule-based dialogue manager, the rhyme planner, a generator (System A, the GRU, or System D, Qwen2.5-1.5B + LoRA) and the reranker. Nothing calls an API at run time.

The design and results are in [pipeline.md](pipeline.md); [ARCHITECTURE.md](ARCHITECTURE.md) maps it to the code and lists what is left.

## Setup

Python 3.10–3.12, from the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For System D on the GPU, install a CUDA build of PyTorch first ([PyTorch's installer](https://pytorch.org/get-started/locally/)).

Copy the trained models from the shared Drive (`MyDrive/CS425/checkpoints`) into `checkpoints/`:

```text
checkpoints/
  nlu_joint_best/            # NLU (Phase 6)
  trait_fit_best/            # reranker trait-fit classifier (Phase 5)
  gen_A_rev_stage2_best.pt   # System A
  gen_D_1.5b_best/           # System D adapter
```

Then fetch the public files (Qwen2.5-1.5B-Instruct base, the MiniLM span encoder, the Detoxify checkpoint, BERT tokenizer files and the GloVe 6B archive, from which `data/glove/` is built) and check that everything is in place:

```powershell
python -m app.setup_assets --download
python -m app.setup_assets
```

The check exits nonzero if something required is missing. The Qwen base is only needed for System D (and the optional Qwen interpreter). If you already have `glove.6B.zip`, `python data/prepare_glove.py path/to/glove.6B.zip` builds `data/glove/` without the download.

## Run

```powershell
python -m app.chat --device cuda      # or --device cpu
```

System D is the default generator (`--system A` to start on the GRU); you can switch in the UI, and switching keeps the conversation's settings. System A runs fine on a CPU (about 4 s per roast); System D is meant for the GPU and is much slower on a CPU. A conversation to try:

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
python -m eval.run_dialogue_eval --mode integrated --system A     # the whole pipeline
```

The dialogue test set is `eval/dialogue_test.jsonl` (24 conversations, 61 turns; `eval/dialogue_dev.jsonl` for development). Results go to `eval/results/dialogue/`; the numbers are in pipeline.md, Phase 9.
