"""Phase 5: train the trait-fit classifier and evaluate it on its test set.

Builds the splits (reranker/trait_fit.py: disses as positives, the 1e negatives plus shuffled disses), fine-tunes
DistilBERT on train, keeps the epoch with the best val AUC (checkpoints/trait_fit_best/), then reports on test, with
training-trait and held-out-trait rows apart: AUC, accuracy / precision / recall / F1 at 0.5, and per row type the
mean score and how often it is scored as a fit, plus the time to score 5 candidates (the reranker runs the classifier
on its top 5 only). Results go to eval/results/trait_fit/ (summary.json, history.json, test_errors.jsonl).

Run from the project root, or on a Colab T4 with reranker/train_trait_fit.ipynb (upload reranker/make_colab_zip.py's zip):
  python reranker/train_trait_fit.py                  # --smoke: a few batches, to check it runs
  python reranker/train_trait_fit.py --eval-only      # re-evaluate checkpoints/trait_fit_best
  python reranker/train_trait_fit.py --ckpt-dir /content/drive/MyDrive/CS425/checkpoints
"""
import argparse, copy, json, shutil, statistics, sys, time
from collections import Counter
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # project root: utils, reranker
from utils import load_config, project_path, set_seed
from reranker.trait_fit import TraitFit, build, build_splits, load, poem_text, predict, scores, train

GROUPS = ("all", "training_traits", "heldout_traits")


def split_counts(rows):
    return {s: dict(Counter(r["type"] for r in v), heldout=sum(r["heldout"] for r in v)) for s, v in rows.items()}


def time_top5(fit, rows, n=20):
    """Seconds to score 5 candidates for one trait set, the reranker's use, averaged over n trait sets."""
    fit.score(rows[0]["traits"], [r["lines"] for r in rows[:5]])     # warm-up
    t = time.time()
    for i in range(n):
        sel = rows[i * 5 % len(rows):][:5]
        fit.score(sel[0]["traits"], [r["lines"] for r in sel])
    return (time.time() - t) / n


def evaluate(model, tok, meta, test, hp, device, out_dir, log=print):
    """The test results above; writes summary.json and test_errors.jsonl to out_dir and returns the summary."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = meta["traits"]
    probs = predict(model, tok, test, info, device, meta["describe_traits"], meta["max_len"])
    masks = {"all": [True] * len(test), "training_traits": [not r["heldout"] for r in test],
             "heldout_traits": [r["heldout"] for r in test]}
    summary = {"model": meta["base_model"], "best_epoch": meta.get("epoch"), "lr": meta.get("lr"),
               "seed": meta.get("seed"), "describe_traits": meta["describe_traits"],
               "test": {g: scores([r for r, m in zip(test, mask) if m], [p for p, m in zip(probs, mask) if m])
                        for g, mask in masks.items()}}

    fit = TraitFit(model, tok, meta, device)
    summary[f"seconds_per_5_candidates_{device}"] = round(time_top5(fit, test), 4)
    if device != "cpu":
        cpu = TraitFit(copy.deepcopy(model).float().cpu(), tok, meta, "cpu")
        summary["seconds_per_5_candidates_cpu"] = round(time_top5(cpu, test, n=5), 4)
        del cpu
    json.dump(summary, open(out_dir / "summary.json", "w"), indent=2)

    with open(out_dir / "test_errors.jsonl", "w", encoding="utf-8") as f:
        for r, p in sorted(zip(test, probs), key=lambda x: -abs(x[1] - x[0]["label"])):
            if (p >= 0.5) != bool(r["label"]):
                f.write(json.dumps({"type": r["type"], "label": r["label"], "score": round(p, 4), "traits": r["traits"],
                                    "about": r["about"], "heldout": r["heldout"], "poem": poem_text(r["lines"])},
                                   ensure_ascii=False) + "\n")

    for g in GROUPS:
        s = summary["test"][g]
        log(f"test {g:16s} n={s['n']:5d} (pos {s['positives']:4d}) AUC {s['auc']:.4f} | acc {s['accuracy']:.3f} "
            f"P {s['precision']:.3f} R {s['recall']:.3f} F1 {s['f1']:.3f}")
    log(f"{'type':14s} " + " ".join(f"{g:>26s}" for g in GROUPS))
    log(f"{'':14s} " + " ".join(f"{'n   mean  scored fit':>26s}" for _ in GROUPS))
    for t in sorted({r["type"] for r in test}):
        cells = []
        for g in GROUPS:
            b = summary["test"][g]["by_type"].get(t)
            cells.append(f"{b['n']:5d} {b['mean_score']:6.3f} {b['scored_fit']:8.3f}".rjust(26) if b else " " * 26)
        log(f"{t:14s} " + " ".join(cells))
    times = {k: v for k, v in summary.items() if k.startswith("seconds")}
    log(f"time to score 5 candidates: {times} | wrote {out_dir}")
    return summary


RUN_KEYS = {"val_auc": "val AUC", "val_f1": "val F1", "test_auc": "test AUC", "test_f1": "test F1",
            "test_auc_heldout": "held AUC", "wrong_trait_fit": "wrong fit", "shuffled_fit": "shuf fit"}


def sweep(rows, hp, lrs, seeds, epochs, device, work_dir, max_batches=None, log=print):
    """One model per (learning rate, seed), each saved to work_dir/lr{lr}_seed{seed}/ and evaluated on test. Returns a
    record per run and the chosen run: the learning rate with the best mean val AUC, then its run with the best val
    AUC. The test results are only reported, never used to choose."""
    info = rows["info"]
    runs = []
    for lr in lrs:
        for seed in seeds:
            name = f"lr{lr:g}_seed{seed}"
            ckpt = Path(work_dir) / name
            set_seed(seed)                                # the new head's initialization and the batch order
            t = time.time()
            model, tok = build(hp["model"])
            hist = train(model, tok, rows["train"], rows["val"], info, hp, device, ckpt, lr=lr, epochs=epochs,
                         seed=seed, max_batches=max_batches, log=lambda *a: None)
            best = max(hist, key=lambda h: h["val_auc"])
            model, tok, meta = load(ckpt, device)
            s = evaluate(model, tok, meta, rows["test"], hp, device, ckpt / "results", log=lambda *a: None)["test"]
            types = s["all"]["by_type"]
            runs.append({"name": name, "lr": lr, "seed": seed, "ckpt": str(ckpt), "best_epoch": best["epoch"],
                         "epochs_run": len(hist), "val_auc": best["val_auc"], "val_f1": best["val_f1"],
                         "test_auc": s["all"]["auc"], "test_f1": s["all"]["f1"],
                         "test_auc_heldout": s["heldout_traits"]["auc"],
                         "wrong_trait_fit": types.get("wrong_trait", {}).get("scored_fit", float("nan")),
                         "shuffled_fit": types.get("shuffled", {}).get("scored_fit", float("nan")), "history": hist})
            r = runs[-1]
            log(f"{name}: best epoch {r['best_epoch']}/{r['epochs_run']} | val AUC {r['val_auc']:.4f} | test AUC "
                f"{r['test_auc']:.4f} (held-out {r['test_auc_heldout']:.4f}) F1 {r['test_f1']:.3f} | "
                f"{time.time() - t:.0f}s")
            del model
            if device == "cuda":
                torch.cuda.empty_cache()
    mean_val = {lr: statistics.mean(r["val_auc"] for r in runs if r["lr"] == lr) for lr in lrs}
    best_lr = max(mean_val, key=mean_val.get)
    chosen = max((r for r in runs if r["lr"] == best_lr), key=lambda r: r["val_auc"])
    return runs, chosen


def sweep_table(runs, log=print):
    """Mean ± standard deviation over seeds for each learning rate. "wrong fit" and "shuf fit": the share of test
    wrong_trait and shuffled negatives scored as a fit (lower is better)."""
    log(f"{'lr':>7} {'runs':>4} " + " ".join(f"{v:>13}" for v in RUN_KEYS.values()))
    for lr in sorted({r["lr"] for r in runs}):
        sel = [r for r in runs if r["lr"] == lr]
        cells = []
        for k in RUN_KEYS:
            v = [r[k] for r in sel]
            sd = statistics.stdev(v) if len(v) > 1 else 0.0
            cells.append(f"{statistics.mean(v):.3f} ± {sd:.3f}".rjust(13))
        log(f"{lr:7g} {len(sel):4d} " + " ".join(cells))


def load_rows(cfg):
    rows, info = build_splits(cfg)
    return {**rows, "info": info}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="a few batches and one epoch, to check the script runs")
    ap.add_argument("--eval-only", action="store_true", help="evaluate the saved checkpoint without training")
    ap.add_argument("--ckpt-dir", default=None, help="default: paths.checkpoints in config.yaml")
    args = ap.parse_args()

    cfg = load_config()
    hp = cfg["trait_fit"]
    seed = set_seed(cfg["seed"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = Path(args.ckpt_dir or project_path(cfg["paths"]["checkpoints"])) / "trait_fit_best"
    out = ckpt.parent / "trait_fit_results" if args.smoke else project_path("eval/results/trait_fit")   # keep the real results
    out.mkdir(parents=True, exist_ok=True)
    rows = load_rows(cfg)
    print("device:", device, "| checkpoint:", ckpt)
    for s, c in split_counts({s: rows[s] for s in ("train", "val", "test")}).items():
        print(f"  {s:5s} {sum(v for k, v in c.items() if k != 'heldout'):5d} {c}")

    if args.smoke:
        rows = {**{s: rows[s][:64] for s in ("train", "val")}, "test": rows["test"][:256], "info": rows["info"]}
    if not args.eval_only:
        model, tok = build(hp["model"])
        train(model, tok, rows["train"], rows["val"], rows["info"], hp, device, ckpt, epochs=1 if args.smoke else None,
              seed=seed, max_batches=3 if args.smoke else None)
        shutil.copy(ckpt / "history.json", out / "history.json")
    model, tok, meta = load(ckpt, device)
    evaluate(model, tok, meta, rows["test"], hp, device, out)


if __name__ == "__main__":
    main()
