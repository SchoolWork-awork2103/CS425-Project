"""Samples disses from a trained System A checkpoint, to look at the output.

    python generation/generate_gru.py --traits lazy funny --intensity harsh --rhymes late wait routine scene
    python generation/generate_gru.py --from-test 5      # prompts from the diss test set instead
"""
import argparse, json, random, sys
from pathlib import Path

import torch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from utils import load_config, project_path
from gru_lm import load_generator, generate, sample_report
from sequences import read_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="checkpoints/gen_A_rev_stage2_best.pt")
    ap.add_argument("--traits", nargs="*", default=["lazy"])
    ap.add_argument("--intensity", default="harsh", choices=["none", "mild", "harsh"])
    ap.add_argument("--rhymes", nargs=4, default=["late", "wait", "bed", "said"], metavar="WORD",
                    help="four line-end words, AABB")
    ap.add_argument("--from-test", type=int, default=0, help="use N random test-set prompts instead")
    ap.add_argument("-n", type=int, default=5, help="poems per prompt")
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-p", type=float, default=0.9)
    ap.add_argument("--rep-penalty", type=float, default=1.2)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    cfg = load_config()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, codec = load_generator(project_path(args.ckpt), cfg, device)
    sampling = dict(temperature=args.temperature, top_p=args.top_p, rep_penalty=args.rep_penalty)

    if args.from_test:
        rows = read_jsonl(project_path(cfg["paths"]["diss_dir"]) / "test.jsonl")
        random.Random(args.seed).shuffle(rows)
        prompts = [{"traits": r["traits"], "intensity": r["intensity"], "end_words": r["end_words"]}
                   for r in rows[:args.from_test]]
        sample_report(model, codec, prompts, device, n=args.n, show=args.n * len(prompts), seed=args.seed,
                      **sampling)
        return

    torch.manual_seed(args.seed)
    samples = generate(model, codec, args.traits, args.intensity, [w.lower() for w in args.rhymes], n=args.n,
                       device=device, **sampling)
    print(f"[{', '.join(args.traits) or 'no traits'} | {args.intensity} | rhymes {' '.join(args.rhymes)}]")
    for s in sorted(samples, key=lambda s: -s["norm_logprob"]):
        print(f"\nlogprob/token {s['norm_logprob']:.2f}")
        for l in s["lines"]:
            print("   " + l)


if __name__ == "__main__":
    main()
