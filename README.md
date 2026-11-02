# Four-line roast chatbot

A local chatbot that turns user traits into playful AABB quatrains. One Qwen2.5-1.5B-Instruct instance interprets messages with its poem LoRA adapter disabled, then writes candidate poems with that adapter enabled. A deterministic dialogue manager owns settings, clarification and history. The reversed-line GRU remains available as System A.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the project status and [AGENTS.md](AGENTS.md) for the implementation checklist.

## Install and prepare assets

Use Python 3.10–3.12. From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For the CUDA demo, install the CUDA-compatible PyTorch build for your machine using [PyTorch's installer](https://pytorch.org/get-started/locally/). The CPU build runs correctly but Qwen and its candidate batches can be slow. No response-time or GPU-memory claim has yet been measured with the project's checkpoints.

Copy the project's trained outputs from the shared `MyDrive/CS425/checkpoints` directory into `checkpoints/`:

```text
checkpoints/
  gen_D_1.5b_best/       # adapter_config.json, adapter_model.safetensors, tokenizer files
  trait_fit_best/       # classifier weights, tokenizer, config.json, trait_fit.json
  gen_A_rev_stage2_best.pt   # optional: System A
  nlu_joint_best/       # optional: existing NLU baseline
```

Keep the Qwen adapter separate from the base weights. Adapter-disabled interpretation relies on PEFT's [disable_adapter context](https://huggingface.co/docs/peft/en/package_reference/peft_model#peft.PeftModel.disable_adapter). If `adapter_config.json` names a different/local base path, make that exact base available locally.

Prepare the public base model, Detoxify checkpoint, BERT tokenizer/config and GloVe vectors while online:

```powershell
python -m app.setup_assets --download
```

This downloads the public dependencies (base model, tokenizers, Detoxify checkpoint and the ~830 MB GloVe 6B archive, from which the compact vectors in `data/glove/` are derived); it does not replace your trained project checkpoints. For the NLU baseline, use `--backend nlu` as well to cache MiniLM. The runtime itself uses local files only. The default Detoxify checkpoint path is `checkpoints/toxic_original-c1212f89.ckpt`; its scores are computed locally from those weights.

If you were offline during setup, copy the team's prepared GloVe `.npy` and `.vocab.txt` files into `data/glove/` instead, or derive them from a local copy of the Stanford `glove.6B.zip` archive:

```powershell
python data/prepare_glove.py path/to/glove.6B.zip
python -m app.setup_assets
```

The asset check exits nonzero when required files are absent. The dialogue code and UI can be inspected/tested without model assets, but actual interpretation and generation require the checkpoints and public caches.

## Run

```powershell
python -m app.chat --device cuda
```

Use `--device cpu` for CPU inference. Select A/D in the UI; switching generators preserves session settings. Qwen interpretation still loads Qwen when System A is selected. Use `--backend nlu` to explicitly select the original DistilBERT/MiniLM interpretation baseline.

Try a conversation such as:

1. `Roast me, I'm confident and musical.`
2. `Another one, but softer.`
3. `Use my punctuality instead.`
4. `Also add how organized I am.`
5. `Reset`

Settings default to `mild`; `harsh` is the other supported value. Unknown descriptions trigger clarification. A generic roast requires an explicit request. Failed selection preserves the resolved settings and does not append history. A poem must pass the four-line, exact AABB, lexical and configured toxicity checks before it is returned.

## Catalogue and configuration

`data/traits.json` is the canonical source for the 40 traits, neutral descriptions and synonyms. `data/trait_catalogue.json` adds counts derived exclusively from the poem training split: 35 traits were seen in fine-tuning and five were held out. All 40 are supported at runtime. Regenerate the catalogue after changing traits or training data:

```powershell
python -m dialogue.build_catalogue
```

Only neutral definitions and synonyms enter the interpretation prompt. The prompt and structured state are supplied afresh on each call. The service serializes access to the shared Qwen model, disables the adapter inside a context manager and restores it even when inference fails. Python validates every proposed operation before committing settings.

The 1.5B interpreter still occasionally emits operations the message did not ask for: echoing session settings back as trait edits, inventing trait keys, or using the user's intensity word instead of mild/harsh. The pipeline therefore enforces deterministic guards around model output: an explicit roast request generates even when the flag is dropped; trait updates that name non-catalogue keys are dropped instead of failing the turn (`interpretation_salvaged` in the trace); remove/replace operations whose traits the message does not name are dropped, while adds are kept and answers to pending questions are exempt (`ungrounded_updates_dropped`); and obvious intensity synonyms (high/strong/meaner, low/soft/gentle/softer) are mapped to the two supported values. The interpreter sees the current settings (intensity, generic, pending question) but never the current trait list, which was the source of the echoed edits.

`config.yaml` controls interpretation budgets, backend selection, candidate sampling, retries and history length. The combined reranker has **provisional weights**, not weights tuned against human ratings. Strict AABB filtering is enabled for the runtime product; it can reject every candidate and return a recoverable failure.

The NLU baseline retains its original seven-intent limitations. It does not infer the new compound add/remove/replace operations or negation; those limitations must remain visible in comparisons.

## Tests and evaluation

```powershell
python -m unittest discover -v
python -m eval.run_dialogue_eval --mode policy
python -m eval.run_dialogue_eval --mode interpreter --backend qwen --device cuda
python -m eval.run_dialogue_eval --mode interpreter --backend nlu --device cpu
python -m eval.run_dialogue_eval --mode integrated --system D --device cuda
python -m eval.run_dialogue_eval --mode integrated --system A --device cuda
```

The **policy** evaluation uses supplied gold interpretations and mocked poem records. Its 23 frozen conversations contain 58 turns. It measures state transitions, not language understanding or poem quality. `eval/dialogue_dev.jsonl` is a separate prompt-development set; select it with `--fixtures`. Keep the test set frozen during prompt iteration. Known fixture anomaly: `collect-and-adjust` turn 1 golds intensity `harsh` although the message names none, so a faithful interpreter can never match that turn.

The **interpreter** mode runs the selected actual interpreter and the policy without poem generation. The **integrated** mode also runs planning, generation and reranking. Results include exact interpretation/trait/operation/intensity counts, clarification and retry rates, state accuracy, conversation completion, latency, CUDA memory where available, dependency versions and source fingerprints. Errors are classified by pipeline stage. JSON compliance is separate from semantic correctness.

Results go to `eval/results/dialogue/`; use `--output` to retain multiple runs. The actual project-checkpoint Qwen interpreter has been measured once here in interpreter mode (prompt trait-operations-v3): 47/55 attempts valid on first try, 52/55 after retry, state accuracy 16/58 against the frozen gold — the model is the weak link, and the pipeline guards above bound the damage from its mistakes. A/D integrated quality, GPU memory and CPU/GPU latency have not yet been evaluated. Qwen is the configured candidate backend; it has not yet been shown to beat the existing NLU baseline.

Unit tests cover malformed interpretations, pending questions, compound changes, explicit generic requests, history, isolation, retry exhaustion, strict ranking, and adapter restoration/concurrent access. Tiny random Qwen/PEFT and BERT models test library compatibility and offline scoring without downloading weights; they are not trained-project-model evaluations. Planner tests skip when GloVe is unavailable.
