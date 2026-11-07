"""Phase 9: the automatic evaluation of Systems A, D and E on the 50 frozen prompts (eval/prompts.json).

python -m eval.run_auto_eval generate --system E --device cuda                  # pool, the planner's rhyme plans
python -m eval.run_auto_eval generate --system E --device cuda --plans random    # pool for the no-planner ablation
python -m eval.run_auto_eval analyse --device cuda                              # every pool found -> metrics

The prompts are frozen: nothing is ever tuned on them. If a setting changes after a look at these results, every
system is run again, and the report says so.

generate: for each prompt and seed, the top reranker.tuning.plans rhyme plans (2) and, for each plan, as many batches
of reranker.tuning.per_plan candidates (10) as the app may use (1 + dialogue.generation_retries = 2), made with the
app's own code and settings (Pipeline._planner and Pipeline._generate in app/pipeline.py, sampling in config.yaml).
Every candidate is saved, so every configuration below picks from the same poems and the comparisons are paired.
  - Input: each prompt's gold traits, so the generators are compared without NLU mistakes (the NLU has its own test
    set and the dialogue eval). intensity null becomes dialogue.default_intensity. The 5 "unclear" prompts have no
    traits: they get a generic roast, as the fallback disses taught every generator, and are reported apart.
  - Seeds: each batch is seeded from (seed, prompt, plan, batch), so a prompt's poems do not depend on run order.
  - --plans random (no-planner ablation): two rhyming end-word pairs from the training disses, with different rhyme
    sounds, fixed per prompt and the same for every system and seed: rhymes the generators know, but unrelated to
    the traits. Leaving the end words out is not an option, since every generator was trained with four.
  - Time: one untimed request first, so loading the models is not counted. Run plugged in: a laptop GPU on battery
    can be several times slower.
  - A run can be stopped and started again: prompt-seed pairs already in the pool are skipped.

analyse: each configuration picks one poem per prompt and seed, the way the app would (Pipeline._respond):
  full         rerank batch 1 (10 per plan); if no candidate is full AABB, batch 2 too, then the best of any rhyme
  no_reranker  the first candidate of plan 1, unfiltered: what the generator alone gives
  k5 ... k40   rerank the first k candidates, plans in turn, as one batch: quality against number of candidates
  no_planner   full, on the random-plan pool
Metrics on the chosen poem (eval/auto_metrics.py): returned, four lines, strict AABB, end-word hit, syllable_score,
lexical_score, trait mention, trait fit (the reranker's DistilBERT), embedding similarity to the trait descriptions
(MiniLM), 4-gram overlap with the training disses and copied lines, distinct-1/2, and time (full only). A request with
no poem scores 0 on returned, four lines, AABB and end-word hit, and is left out of the rest. The reranker chooses by
trait fit, so trait mention and embedding similarity are the fairer trait measures for configurations with it.
Per prompt, metrics are averaged over seeds; intervals are 95% bootstrap over prompts, and comparisons are paired.

Files in eval/results/auto/: <system>_<plans>_pool.jsonl (every candidate) with <system>_<plans>_pool.meta.json (how
it was made), summary.json (every metric, overall and per category) and comparison.json (paired differences).
"""
import argparse
from collections import defaultdict
from datetime import date
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import time

from app.pipeline import GENERATORS, Pipeline
from dialogue.catalogue import ROOT
from eval import auto_metrics as M
from eval.run_dialogue_eval import checkpoint_record
from phonetics import lexical_score, rhymes, same_sound, syllable_score
from utils import load_config

OUT = ROOT / "eval/results/auto"
CONFIGS = ["full", "no_reranker", "k5", "k10", "k20", "k40", "no_planner"]
METRICS = ["returned", "four_lines", "aabb", "end_word_hit", "syllables", "lexical", "mention", "trait_fit",
           "embedding", "overlap", "copied_line", "seconds"]
COMPARED = ["returned", "aabb", "end_word_hit", "syllables", "lexical", "mention", "trait_fit", "embedding", "overlap"]


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def load_prompts(cfg, limit=None):
    prompts = json.loads((ROOT / cfg["paths"]["eval_prompts"]).read_text(encoding="utf-8"))
    default = cfg["dialogue"]["default_intensity"]
    return [{**p, "intensity": p["intensity"] or default} for p in prompts][:limit]


def random_plans(cfg, prompts, k):
    """k random rhyme plans per prompt from the training disses' own rhyming end-word pairs (--plans random)."""
    rows = read_jsonl(ROOT / cfg["paths"]["diss_dir"] / "train.jsonl")
    pairs = sorted({(r["end_words"][i], r["end_words"][i + 1]) for r in rows for i in (0, 2)
                    if rhymes(r["end_words"][i], r["end_words"][i + 1])})
    plans = {}
    for p in prompts:
        rng, chosen = random.Random(f"random-plan-{p['id']}"), []
        while len(chosen) < k:
            a, b = rng.sample(pairs, 2)
            if not same_sound(a[0], b[0]) and len({*a, *b}) == 4:
                chosen.append([*a, *b])
        plans[p["id"]] = chosen
    return plans


def pool_path(out, system, plans):
    return Path(out) / f"{system}_{plans}_pool.jsonl"


def generate(cfg, system, device, plans_mode="planner", seeds=(0, 1, 2), limit=None, out=OUT):
    import torch
    t = cfg["reranker"]["tuning"]
    k, per_plan, batches = t["plans"], t["per_plan"], 1 + cfg["dialogue"]["generation_retries"]
    prompts = load_prompts(cfg, limit)
    pipeline = Pipeline(cfg, system, device)
    plans = (random_plans(cfg, prompts, k) if plans_mode == "random"
             else {p["id"]: [x["end_words"] for x in pipeline._planner().plan(p["traits"], k=k)] for p in prompts})
    path = pool_path(out, system, plans_mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = {(r["prompt"], r["seed"]) for r in read_jsonl(path)} if path.exists() else set()

    first = prompts[0]                                  # loads the models; not timed
    pipeline._generate(system, first["traits"], first["intensity"], plans[first["id"]][0])
    with path.open("a", encoding="utf-8") as stream:
        for seed in seeds:
            for p in prompts:
                if (p["id"], seed) in done:
                    continue
                row = {"prompt": p["id"], "seed": seed, "system": system, "plans": plans[p["id"]], "candidates": [],
                       "seconds": [], "error": None}
                try:
                    for j, end_words in enumerate(plans[p["id"]]):
                        row["seconds"].append([])
                        for b in range(batches):
                            torch.manual_seed(1_000_003 * seed + 1000 * p["id"] + 10 * j + b)
                            start = time.perf_counter()
                            batch = pipeline._generate(system, p["traits"], p["intensity"], end_words)
                            row["seconds"][j].append(time.perf_counter() - start)
                            row["candidates"] += [{"plan": j, "batch": b, "sample": i, "lines": c["lines"],
                                                   "norm_logprob": c["norm_logprob"]} for i, c in enumerate(batch)]
                except (OSError, RuntimeError, ValueError) as exc:
                    row["error"] = f"{type(exc).__name__}: {exc}"
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(f"{system} seed {seed} prompt {p['id']}: {len(row['candidates'])} candidates"
                      f"{' | ' + row['error'] if row['error'] else ''}")

    versions = {}
    for name in ("torch", "transformers", "peft"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    meta = {"date": date.today().isoformat(), "system": system, "plans": plans_mode, "seeds": list(seeds),
            "device": device, "gpu": torch.cuda.get_device_name() if device == "cuda" else None,
            "prompts_sha256": hashlib.sha256((ROOT / cfg["paths"]["eval_prompts"]).read_bytes()).hexdigest(),
            "checkpoint": checkpoint_record(cfg, system), "versions": versions, "sampling": cfg.get("sampling"),
            "plans_per_prompt": k, "per_plan": per_plan, "batches": batches}
    path.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def config_batches(row, config, batches):
    """The candidate batches a configuration reranks, from one pool row (plans x batches x per_plan candidates)."""
    cands = [{**c, "planned_end_words": row["plans"][c["plan"]]} for c in row["candidates"]]
    if config in ("full", "no_planner"):
        return [[c for c in cands if c["batch"] == b] for b in range(batches)]
    if config.startswith("k"):
        by_plan = [sorted((c for c in cands if c["plan"] == j), key=lambda c: (c["batch"], c["sample"]))
                   for j in range(len(row["plans"]))]
        return [M.interleave(by_plan, int(config[1:]))]
    raise ValueError(config)


def poem_metrics(chosen, traits, info, vocab, train):
    if chosen is None:
        return {"returned": 0, "four_lines": 0, "aabb": 0, "end_word_hit": 0}
    lines = chosen["lines"]
    return {"returned": 1, "four_lines": int(len(lines) == 4 and all(l.strip() for l in lines)),
            "aabb": int(M.strict_aabb(lines)), "end_word_hit": M.end_word_hit(lines, chosen["planned_end_words"]),
            "syllables": syllable_score(lines), "lexical": lexical_score(lines, vocab),
            "mention": None if not traits else int(M.mentions(lines, M.trait_terms(traits, info))),
            **M.memorization(lines, *train)}


def analyse(cfg, device="cpu", out=OUT, bootstrap=2000):
    from reranker.rerank import Reranker
    from sentence_transformers import SentenceTransformer
    from reranker.trait_fit import trait_text
    out = Path(out)
    info = json.loads((ROOT / cfg["paths"]["traits"]).read_text(encoding="utf-8"))
    prompts = {p["id"]: p for p in load_prompts(cfg)}
    batches = 1 + cfg["dialogue"]["generation_retries"]
    reranker = Reranker(cfg, device=device)
    train = M.training_ngrams(read_jsonl(ROOT / cfg["paths"]["diss_dir"] / "train.jsonl"))
    encoder = SentenceTransformer(cfg["nlu"]["span_encoder"], device=device)

    # records[(system, config)][prompt][seed] = metrics; chosen[(system, config)][seed] = poems, for distinct-n
    records, chosen_poems = defaultdict(lambda: defaultdict(dict)), defaultdict(lambda: defaultdict(list))
    for system in GENERATORS:
        pipeline = Pipeline(cfg, system, device, reranker=reranker)
        for plans_mode in ("planner", "random"):
            path = pool_path(out, system, plans_mode)
            if not path.exists():
                continue
            configs = ["no_planner"] if plans_mode == "random" else [c for c in CONFIGS if c != "no_planner"]
            for row in read_jsonl(path):
                p = prompts.get(row["prompt"])
                if p is None or row["error"]:
                    continue
                for config in configs:
                    start = time.perf_counter()
                    if config == "no_reranker":
                        first = next(c for c in row["candidates"] if (c["plan"], c["batch"], c["sample"]) == (0, 0, 0))
                        best, used = {**first, "planned_end_words": row["plans"][0]}, 1
                    else:
                        best, used, _ = M.choose(config_batches(row, config, batches),
                                                 lambda c: reranker.rerank(p["traits"], c), pipeline._select)
                    m = poem_metrics(best, p["traits"], info, reranker.vocab, train)
                    if config in ("full", "no_planner"):             # generation of the batches used + reranking
                        m["seconds"] = sum(s[b] for s in row["seconds"] for b in range(used)) + time.perf_counter() - start
                    if best is not None and p["traits"]:
                        m["trait_fit"] = reranker.trait_fit(p["traits"], [best["lines"]])[0]
                        e = encoder.encode([" ".join(best["lines"]), *[trait_text([t], info) for t in p["traits"]]],
                                           normalize_embeddings=True)
                        m["embedding"] = float((e[1:] @ e[0]).mean())
                    records[(system, config)][row["prompt"]][row["seed"]] = m
                    if best is not None:
                        chosen_poems[(system, config)][row["seed"]].append(best["lines"])
            print(f"analysed {path.name}")

    groups = {"all": list(prompts), **{c: [i for i, p in prompts.items() if p["category"] == c]
                                       for c in ("single", "multi", "heldout", "unclear")}}
    per_prompt = {key: {m: {pid: M.mean([s.get(m) for s in seeds.values()]) for pid, seeds in by_prompt.items()}
                        for m in METRICS} for key, by_prompt in records.items()}
    summary = {}
    for (system, config), values in per_prompt.items():
        res = {g: {m: M.bootstrap_ci([values[m].get(i) for i in ids], bootstrap) for m in METRICS}
               for g, ids in groups.items()}
        seeds = chosen_poems[(system, config)]
        res["distinct"] = {f"distinct_{n}": {"mean": M.mean([M.distinct(seeds[s], n) for s in seeds]),
                                             "seed_sd": M.spread([M.distinct(seeds[s], n) for s in seeds])}
                           for n in (1, 2)}
        by_seed = defaultdict(list)
        for by in records[(system, config)].values():
            for s, m in by.items():
                by_seed[s].append(m["aabb"])
        res["aabb_seed_sd"] = M.spread([M.mean(v) for v in by_seed.values()])
        res["seeds"] = sorted(by_seed)
        summary.setdefault(system, {})[config] = res

    comparison = {}
    pairs = [((s, "full"), (s, c)) for s in GENERATORS for c in CONFIGS if c != "full"]
    pairs += [((a, "full"), (b, "full")) for a in GENERATORS for b in GENERATORS if a < b]
    for x, y in pairs:
        if x in per_prompt and y in per_prompt:
            comparison[f"{x[0]} {x[1]} vs {y[0]} {y[1]}"] = {
                m: M.paired(per_prompt[x][m], per_prompt[y][m], bootstrap) for m in COMPARED}

    out.mkdir(parents=True, exist_ok=True)
    stamp = {"date": date.today().isoformat(), "bootstrap": bootstrap,
             "pools": sorted(p.name for p in out.glob("*_pool.jsonl"))}
    (out / "summary.json").write_text(json.dumps({**stamp, "results": summary}, indent=2) + "\n", encoding="utf-8")
    (out / "comparison.json").write_text(json.dumps({**stamp, "comparisons": comparison}, indent=2) + "\n",
                                         encoding="utf-8")
    print_table(summary)
    print(f"wrote {out / 'summary.json'} and {out / 'comparison.json'}")


def print_table(summary):
    fmt = lambda r, m, pct=True: "-" if r[m]["mean"] is None else (f"{r[m]['mean']:.0%}" if pct else f"{r[m]['mean']:.2f}")
    print(f"\n{'system config':22} {'n':>3} {'poem':>5} {'AABB':>5} {'ends':>5} {'trait':>6} {'held':>5} "
          f"{'fit':>5} {'emb':>5} {'dist2':>5} {'4gram':>6} {'time':>6}")
    for system, configs in summary.items():
        for config, r in configs.items():
            a, h = r["all"], r["heldout"]
            print(f"{system + ' ' + config:22} {a['returned']['n']:>3} {fmt(a, 'returned'):>5} {fmt(a, 'aabb'):>5} "
                  f"{fmt(a, 'end_word_hit'):>5} {fmt(a, 'mention'):>6} {fmt(h, 'mention'):>5} "
                  f"{fmt(a, 'trait_fit', False):>5} {fmt(a, 'embedding', False):>5} "
                  f"{r['distinct']['distinct_2']['mean'] or 0:>5.2f} {fmt(a, 'overlap'):>6} "
                  f"{'-' if a['seconds']['mean'] is None else format(a['seconds']['mean'], '.1f') + ' s':>6}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--system", choices=list(GENERATORS), required=True)
    g.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    g.add_argument("--plans", choices=["planner", "random"], default="planner")
    g.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    g.add_argument("--limit", type=int, default=None, help="first n prompts only (a smoke test)")
    g.add_argument("--out", type=Path, default=OUT)
    a = sub.add_parser("analyse")
    a.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    a.add_argument("--out", type=Path, default=OUT)
    a.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    cfg = load_config()
    if args.cmd == "generate":
        generate(cfg, args.system, args.device, args.plans, args.seeds, args.limit, args.out)
    else:
        analyse(cfg, args.device, args.out, args.bootstrap)


if __name__ == "__main__":
    main()
