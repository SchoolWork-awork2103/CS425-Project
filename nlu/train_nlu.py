"""Phase 6: train the joint intent + slot model and evaluate the NLU on its test set.

Trains DistilBERT on data/nlu/corpus/train.jsonl, keeps the best epoch on val (checkpoints/nlu_joint_best/), then
reports on test, with training-trait and held-out-trait messages apart:
  intent accuracy (and the confusions), slot precision / recall / F1 by exact span match,
  trait normalization of the gold spans (strict, and lenient: a trait from the same CLOSE group as the label counts,
  e.g. calm for easygoing), end to end: the traits found in a message against its labels, and the time per message.
Results go to eval/results/nlu/ (summary.json, history.json, test_errors.jsonl).

Trained on a Colab T4 with nlu/train_nlu.ipynb (upload the zip from nlu/make_colab_zip.py), which runs sweep().
From the project root, a single run:
  python nlu/train_nlu.py                      # --smoke: a few batches, to check it runs
  python nlu/train_nlu.py --eval-only          # re-evaluate checkpoints/nlu_joint_best
  python nlu/train_nlu.py --ckpt-dir /content/drive/MyDrive/CS425/checkpoints
"""
import argparse, json, shutil, statistics, sys, time
from collections import Counter
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))                      # project root: utils, nlu
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "negatives"))   # the CLOSE trait groups
from utils import load_config, project_path, set_seed
from nlu.joint_model import NLU, build, load, predict, scores, train
from nlu.normalize import TraitNormalizer, spans_of
from prepare_negatives import close_to


def read_jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def gold_spans(rows):
    """(span text, labelled trait) for every gold span, from rows whose span count matches their trait list."""
    out = []
    for r in rows:
        found = spans_of(r["tokens"], r["tags"])
        if len(found) == len(r["traits"]):
            out += [(" ".join(s), t) for s, t in zip(found, r["traits"])]
    return out


def trait_scores(pairs, preds):
    hows = Counter(p["how"] for p in preds)
    return {"n": len(pairs), "strict": sum(p["trait"] == t for (_, t), p in zip(pairs, preds)) / max(len(pairs), 1),
            "lenient": sum(p["trait"] in close_to(t) for (_, t), p in zip(pairs, preds)) / max(len(pairs), 1),
            "by_rule": dict(hows)}


def evaluate(model, tok, test, traits, hp, device, out_dir, best_epoch=None, norm=None, log=print):
    """All the test results above; writes summary.json and test_errors.jsonl to out_dir and returns the summary.
    norm: a TraitNormalizer to reuse (it does not depend on the model), else one is built."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    heldout = {t for t, v in traits.items() if v["heldout"]}
    preds = predict(model, tok, [r["tokens"] for r in test], device, max_len=hp["max_len"])
    is_held = [bool(set(r["traits"]) & heldout) for r in test]
    groups = {"all": [True] * len(test), "training_traits": [not h for h in is_held], "heldout_traits": is_held}
    summary = {"model": hp["model"], "best_epoch": best_epoch,
               "test": {g: scores([r for r, m in zip(test, mask) if m], [p for p, m in zip(preds, mask) if m])
                        for g, mask in groups.items()}}
    summary["test"]["per_intent_acc"] = {
        i: sum(p["intent"] == i for r, p in zip(test, preds) if r["intent"] == i) /
           max(sum(r["intent"] == i for r in test), 1) for i in sorted({r["intent"] for r in test})}
    summary["test"]["intent_confusions"] = {f"{a} -> {b}": n for (a, b), n in Counter(
        (r["intent"], p["intent"]) for r, p in zip(test, preds) if r["intent"] != p["intent"]).most_common()}

    # trait normalization on the gold spans, and end to end on the predicted ones
    norm = norm or TraitNormalizer()
    nlu = NLU(model, tok, norm, device)
    pairs = gold_spans(test)
    normed = norm.many([s for s, _ in pairs])
    summary["normalization_gold_spans"] = {}
    for g in ("training_traits", "heldout_traits"):
        sel = [(a, b) for a, b in zip(pairs, normed) if (a[1] in heldout) == (g == "heldout_traits")]
        summary["normalization_gold_spans"][g] = trait_scores([a for a, _ in sel], [b for _, b in sel])

    # end to end: exact = the same set of traits; lenient = every label has a found trait in its CLOSE group and
    # every found trait is in the CLOSE group of a label (an unknown span counts as wrong)
    with_traits = [r for r in test if r["traits"]]
    t0 = time.time()
    parsed = [nlu.parse(r["text"]) for r in with_traits]
    per_msg = (time.time() - t0) / max(len(with_traits), 1)
    end = {}
    for g in ("training_traits", "heldout_traits"):
        sel = [(r["traits"], [x["trait"] for x in p["traits"]]) for r, p in zip(with_traits, parsed)
               if bool(set(r["traits"]) & heldout) == (g == "heldout_traits")]
        exact = sum(set(found) == set(gold) for gold, found in sel)
        lenient = sum(bool(found) and all(any(f in close_to(t) for f in found) for t in gold)
                      and all(any(f in close_to(t) for t in gold) for f in found) for gold, found in sel)
        end[g] = {"n": len(sel), "exact_set": exact / max(len(sel), 1), "lenient_set": lenient / max(len(sel), 1),
                  "no_trait_found": sum(not found for _, found in sel) / max(len(sel), 1)}
    summary["end_to_end_traits"] = end
    summary[f"seconds_per_message_{device}"] = round(per_msg, 4)
    json.dump(summary, open(out_dir / "summary.json", "w"), indent=2)

    with open(out_dir / "test_errors.jsonl", "w", encoding="utf-8") as f:
        for r, p in zip(test, preds):
            if p["intent"] != r["intent"] or p["tags"] != r["tags"]:
                f.write(json.dumps({"text": r["text"], "intent": r["intent"], "pred_intent": p["intent"],
                                    "gold_spans": [" ".join(s) for s in spans_of(r["tokens"], r["tags"])],
                                    "pred_spans": [" ".join(s) for s in spans_of(r["tokens"], p["tags"])]},
                                   ensure_ascii=False) + "\n")

    for g, s in summary["test"].items():
        if "intent_acc" in s:
            log(f"test {g:16s} n={s['n']:4d} intent acc {s['intent_acc']:.3f} | slot P {s['slot_precision']:.3f} "
                f"R {s['slot_recall']:.3f} F1 {s['slot_f1']:.3f} (per word {s['slot_word_f1']:.3f}, "
                f"overlap {s['slot_overlap_f1']:.3f})")
    for g, s in summary["normalization_gold_spans"].items():
        log(f"normalization {g:16s} n={s['n']:4d} strict {s['strict']:.3f} lenient {s['lenient']:.3f} {s['by_rule']}")
    for g, s in end.items():
        log(f"end to end    {g:16s} n={s['n']:4d} exact {s['exact_set']:.3f} lenient {s['lenient_set']:.3f} "
            f"none found {s['no_trait_found']:.3f}")
    log(f"{per_msg * 1000:.0f} ms per message on {device} | wrote {out_dir}")
    return summary


RUN_KEYS = {"val_score": "val score", "val_intent_acc": "val intent", "val_slot_word_f1": "val word F1",
            "test_intent_acc": "test intent", "test_slot_f1": "slot F1", "test_slot_word_f1": "word F1",
            "test_slot_overlap_f1": "overlap F1", "traits_exact_training": "traits seen", "traits_exact_heldout": "traits held"}


def sweep(rows, traits, hp, lrs, seeds, epochs, device, work_dir, max_batches=None, log=print):
    """One model per (learning rate, seed), each saved to work_dir/lr{lr}_seed{seed}/ and evaluated on test. Returns a
    record per run and the chosen run: the learning rate with the best mean val score, then its run with the best val
    score. The test results are only reported, never used to choose."""
    norm = TraitNormalizer()
    runs = []
    for lr in lrs:
        for seed in seeds:
            name = f"lr{lr:g}_seed{seed}"
            ckpt = Path(work_dir) / name
            set_seed(seed)                                # the new heads' initialization and the batch order
            t = time.time()
            model, tok = build(hp["model"])
            hist = train(model, tok, rows["train"], rows["val"], device, ckpt, lr=lr, epochs=epochs,
                         batch_size=hp["batch_size"], patience=hp["patience"], max_len=hp["max_len"], seed=seed,
                         max_batches=max_batches, log=lambda *a: None)
            best = max(hist, key=lambda h: h["val_score"])
            model, tok = load(ckpt, device)
            s = evaluate(model, tok, rows["test"], traits, hp, device, ckpt / "results", best["epoch"], norm=norm,
                         log=lambda *a: None)
            runs.append({"name": name, "lr": lr, "seed": seed, "ckpt": str(ckpt), "best_epoch": best["epoch"],
                         "epochs_run": len(hist), "val_score": best["val_score"],
                         "val_intent_acc": best["val_intent_acc"], "val_slot_word_f1": best["val_slot_word_f1"],
                         "test_intent_acc": s["test"]["all"]["intent_acc"], "test_slot_f1": s["test"]["all"]["slot_f1"],
                         "test_slot_word_f1": s["test"]["all"]["slot_word_f1"],
                         "test_slot_overlap_f1": s["test"]["all"]["slot_overlap_f1"],
                         "traits_exact_training": s["end_to_end_traits"]["training_traits"]["exact_set"],
                         "traits_exact_heldout": s["end_to_end_traits"]["heldout_traits"]["exact_set"],
                         "history": hist})
            r = runs[-1]
            log(f"{name}: best epoch {r['best_epoch']}/{r['epochs_run']} | val {r['val_score']:.4f} | test intent "
                f"{r['test_intent_acc']:.3f} slot F1 {r['test_slot_f1']:.3f} word {r['test_slot_word_f1']:.3f} | "
                f"{time.time() - t:.0f}s")
            del model
            if device == "cuda":
                torch.cuda.empty_cache()
    mean_val = {lr: statistics.mean(r["val_score"] for r in runs if r["lr"] == lr) for lr in lrs}
    best_lr = max(mean_val, key=mean_val.get)
    chosen = max((r for r in runs if r["lr"] == best_lr), key=lambda r: r["val_score"])
    return runs, chosen


def sweep_table(runs, log=print):
    """Mean ± standard deviation over seeds for each learning rate. Test columns: intent accuracy, slot F1 (exact, per
    word, overlap) and the traits found end to end (exact set) for training-trait and held-out-trait messages."""
    log(f"{'lr':>7} {'runs':>4} " + " ".join(f"{v:>13}" for v in RUN_KEYS.values()))
    for lr in sorted({r["lr"] for r in runs}):
        sel = [r for r in runs if r["lr"] == lr]
        cells = []
        for k in RUN_KEYS:
            v = [r[k] for r in sel]
            sd = statistics.stdev(v) if len(v) > 1 else 0.0
            cells.append(f"{statistics.mean(v):.3f} ± {sd:.3f}".rjust(13))
        log(f"{lr:7g} {len(sel):4d} " + " ".join(cells))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="a few batches and one epoch, to check the script runs")
    ap.add_argument("--eval-only", action="store_true", help="evaluate the saved checkpoint without training")
    ap.add_argument("--ckpt-dir", default=None, help="default: paths.checkpoints in config.yaml")
    args = ap.parse_args()

    cfg = load_config()
    hp = cfg["nlu"]
    seed = set_seed(cfg["seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = Path(args.ckpt_dir or project_path(cfg["paths"]["checkpoints"])) / "nlu_joint_best"
    out = ckpt.parent / "nlu_results" if args.smoke else project_path("eval/results/nlu")   # keep the real results
    out.mkdir(parents=True, exist_ok=True)
    nlu_dir = project_path(cfg["paths"]["nlu_dir"])
    rows = {s: read_jsonl(nlu_dir / f"{s}.jsonl") for s in ("train", "val", "test")}
    traits = json.load(open(project_path(cfg["paths"]["traits"]), encoding="utf-8"))
    print("device:", device, "| sizes:", {s: len(v) for s, v in rows.items()}, "| checkpoint:", ckpt)

    if args.smoke:
        rows = {s: v[:64] for s, v in rows.items()}
    if not args.eval_only:
        model, tok = build(hp["model"])
        train(model, tok, rows["train"], rows["val"], device, ckpt, lr=hp["lr"], epochs=1 if args.smoke else hp["epochs"],
              batch_size=hp["batch_size"], patience=hp["patience"], max_len=hp["max_len"], seed=seed,
              max_batches=3 if args.smoke else None)
        shutil.copy(ckpt / "history.json", out / "history.json")
    model, tok = load(ckpt, device)
    evaluate(model, tok, rows["test"], traits, hp, device, out, json.load(open(ckpt / "labels.json"))["epoch"])


if __name__ == "__main__":
    main()
