"""Phase 9: the human evaluation, in Google Forms.

python -m eval.human_eval forms --raters 5      # -> data/human_eval/: items.jsonl (the key), build_forms.gs, guide
  Then: open script.google.com, New project, paste build_forms.gs over the code, Save. Choose buildRater1 and Run
  (allow access when asked), then buildRater2, and so on: one rater per run, under Apps Script's 6-minute limit.
  Each run creates that rater's 3 Google Forms, one per part, and logs only the links to answer them (Execution log);
  send each rater their own three links, in order. Every form also writes to one spreadsheet, "Rate the roast poems
  (responses)", one tab per rater and part. When all have submitted, turn off "Accepting responses" in each form,
  then download each tab (File -> Download -> CSV) as data/human_eval/responses/rater_<k>_part<p>.csv.
python -m eval.human_eval collect               # -> eval/results/human/summary.json

Each part is its own form, submitted before the break, so a rater who is not signed in to Google (Google Forms only
keeps drafts for signed-in users) loses at most the part they are in if they close the page.

The poems are the ones the automatic evaluation chose for seed 425 (eval/results/auto/chosen.jsonl, from
`python -m eval.run_auto_eval analyse`), so people rate exactly the poems the automatic metrics scored:
  - 30 of the 50 frozen prompts, drawn with a fixed seed: all 5 held-out, 12 single-trait, 12 multi-trait, 1 unclear
  - 4 configurations per prompt: D-full, E-full, A-full (the app as used) and D-base (D's first candidate with random
    rhyme words and no reranker, under the toxicity limits), so 120 poems; a poem two configurations share is shown
    once and its ratings count for both
  - 5 criteria, 1 to 5, with anchors in the guide: coherence, relevance, humour, poetic quality, rhyme
Every rater rates every poem (agreement needs that), blind: poems carry a random number and nothing else. A request's
four poems are shown together on one page, each rated on its own; requests come in each rater's own random order, in
3 parts (forms) of 10 with a break between, part 1 starting with 2 practice poems that are not counted.

collect checks the responses (every rating present and 1-5), then reports per configuration and criterion the mean
rating (averaged over raters per poem) with a 95% bootstrap interval over prompts, held-out traits apart; rater
agreement (Krippendorff's alpha, ordinal) per criterion; paired Wilcoxon tests D-full vs E-full, D-full vs A-full,
E-full vs A-full and D-full vs D-base with Holm-adjusted p-values (4 comparisons x 5 criteria); and how the automatic
metrics agree with the ratings (Spearman over poems).
"""
import argparse
import csv
from collections import defaultdict
import json
from pathlib import Path
import random
import re
import statistics
import sys

from dialogue.catalogue import ROOT
from eval import auto_metrics as M
from utils import load_config

DIR, RESULTS = ROOT / "data/human_eval", ROOT / "eval/results/human"
CHOSEN = ROOT / "eval/results/auto/chosen.jsonl"
CONFIGS = [("D", "full"), ("E", "full"), ("A", "full"), ("D", "base")]
COMPARISONS = [("D-full", "E-full"), ("D-full", "A-full"), ("E-full", "A-full"), ("D-full", "D-base")]
CRITERIA = ["Coherence", "Relevance", "Humour", "Poetic quality", "Rhyme"]
MIX = {"heldout": 5, "single": 12, "multi": 12, "unclear": 1}
POEM_SEED, PARTS = 425, 3
TITLE = "Rate the roast poems"
TITLE_RE = re.compile(r"^Poem #(\d+) \[(.+)\]$")
# automatic metric -> the criterion it should track, for the human-automatic agreement
AUTOMATIC = [("aabb", "Rhyme"), ("end_word_hit", "Rhyme"), ("mention", "Relevance"), ("embedding", "Relevance"),
             ("trait_fit", "Relevance"), ("lexical", "Coherence"), ("syllables", "Poetic quality")]

INTRO = """Thank you for helping! A chatbot writes short roast poems: someone tells it what they are proud of, and it
answers with a four-line poem that teases them about it. Several versions of the bot wrote the poems you will see.

There are 30 requests, each with up to 4 poems, in 3 parts of 10 requests: this form is one part, and you have a
separate link for each. Rate every poem from 1 to 5 on five criteria. Each part takes about 15-20 minutes. Submit a
part before taking a break: an unsubmitted form is lost if you close the page. Part 1 starts with two practice poems.

The poems are playful insults. They were filtered for vulgar and hateful language, but they are still roasts."""

GUIDE = """Rate each poem on its own, from 1 to 5 (2 and 4 are for in-between cases):

Coherence: does it make sense?
  1 nonsense or broken sentences / 3 mostly makes sense, one line clumsy or confusing / 5 every line makes sense and
  the lines connect
Relevance: is it about the requested traits?
  1 not about the traits / 3 loosely about them, or a generic roast / 5 clearly about the traits, turning the brag
  against the person
  "harsh" should bite and "mild" should be gentle teasing: a clear mismatch costs a point here. For a request with
  no trait, relevance means a fair generic roast.
Humour: is it funny?
  1 flat, or mean without wit / 3 mildly amusing / 5 genuinely funny, with a real punchline
Poetic quality: does it flow?
  1 clunky, uneven lines, words forced in to rhyme / 3 readable but forced in places / 5 flows naturally, nothing
  forced
Rhyme: do lines 1-2 rhyme, and lines 3-4?
  1 neither pair rhymes / 3 one pair rhymes, or near-rhymes / 5 both pairs clearly rhyme

Rate alone, and don't look anything up. There are no right answers: we want your own opinion."""

SCRIPT = """// Built by eval/human_eval.py. At script.google.com: New project, paste this over the code, Save.
// Then choose buildRater1 and Run, then buildRater2, and so on: one rater per run, since Apps Script stops a run
// after 6 minutes and all raters in one run could pass that. Each run makes that rater's 3 forms and logs the
// links to send them (Execution log). If a run stops partway, delete the forms it made (Google Drive) and run it
// again. Every form also writes its responses to one spreadsheet, "<title> (responses)", a tab per rater and part:
// download each tab (File > Download > CSV) as data/human_eval/responses/rater_<k>_part<p>.csv.
// Only the buildRater<k> functions show in the Run menu: the helpers end in "_", which keeps them out of it.
__RUNNERS__

const DATA = __DATA__;

function addPoem_(form, title, lines) {
  form.addGridItem().setTitle(title).setHelpText(lines.join('\\n'))
      .setRows(DATA.criteria).setColumns(['1', '2', '3', '4', '5']).setRequired(true);
}

// The spreadsheet every form writes to, made on the first run and kept in the script's properties.
function responsesSheet_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('responses');
  if (id) return SpreadsheetApp.openById(id);
  const sheet = SpreadsheetApp.create(DATA.title + ' (responses)');
  props.setProperty('responses', sheet.getId());
  return sheet;
}

function buildRater_(k) {
  const r = DATA.raters.filter(function (x) { return x.rater === k; })[0];
  if (!r) throw new Error('No rater ' + k);
  const sheet = responsesSheet_();
  const links = [], tabs = {};
  r.parts.forEach(function (part, i) {
      const name = 'part ' + (i + 1) + ' of ' + r.parts.length;
      const form = FormApp.create(DATA.title + ' (rater ' + r.rater + ', ' + name + ')');
      form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());
      tabs[form.getId()] = 'rater_' + r.rater + '_part' + (i + 1);
      form.setDescription(DATA.intro).setProgressBar(true).setCollectEmail(false)
          .setShowLinkToRespondAgain(false).setConfirmationMessage(i + 1 < r.parts.length
              ? 'Thank you, part ' + (i + 1) + ' is saved. Take a break if you like, then open the link for part ' +
                (i + 2) + '.'
              : 'Thank you, all your ratings are saved.');
      form.addSectionHeaderItem().setTitle('How to rate').setHelpText(DATA.guide);
      if (i === 0) {
        form.addPageBreakItem().setTitle('Practice').setHelpText(
            'Two practice poems to get used to the scale. They are not counted.\\n\\n' + r.practice.request);
        r.practice.poems.forEach(function (p, k) { addPoem_(form, 'Practice poem ' + (k + 1), p); });
      }
      part.forEach(function (req, j) {
        form.addPageBreakItem().setTitle('Request ' + (j + 1) + ' of ' + part.length + ' (' + name + ')')
            .setHelpText('Request: ' + req.request + '\\nIntensity: ' + req.intensity +
                         '\\n\\nRate each poem below from 1 to 5 (the guide is on the first page).');
        req.poems.forEach(function (p) { addPoem_(form, p.title, p.lines); });
      });
      links.push('  part ' + (i + 1) + ': ' + form.getPublishedUrl());
  });
  // name the new response tabs after their rater and part (the forms still work if this fails)
  try {
    SpreadsheetApp.flush();
    sheet.getSheets().forEach(function (s) {
      const url = s.getFormUrl();
      const tab = url && tabs[FormApp.openByUrl(url).getId()];
      if (tab) s.setName(tab);
    });
  } catch (e) {
    Logger.log('Could not rename the response tabs (' + e + '); they are named "Form Responses <n>".');
  }
  // Only the links to answer the forms: the forms themselves are in your Google Drive, not in this log.
  Logger.log('Rater ' + r.rater + ' (send these, in order):\\n' + links.join('\\n'));
}
"""


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def request_text(traits):
    return ", ".join(traits) if traits else "(no trait: a generic roast)"


def build_items(chosen, seed):
    """(the 30 prompts, the poems to rate, practice poems, missing poems) from chosen.jsonl's rows for POEM_SEED."""
    rows = {(r["system"], r["config"], r["prompt"]): r for r in chosen if r["seed"] == POEM_SEED}
    prompts = {r["prompt"]: r for r in rows.values()}
    rng = random.Random(seed)
    by_cat = defaultdict(list)
    for pid in sorted(prompts):
        by_cat[prompts[pid]["category"]].append(pid)
    selected = sorted(pid for cat, n in MIX.items() for pid in rng.sample(by_cat[cat], n))

    items, missing = [], []
    for pid in selected:
        for system, config in CONFIGS:
            row = rows.get((system, config, pid))
            if row is None or row["lines"] is None:
                missing.append({"prompt": pid, "config": f"{system}-{config}"})
                continue
            same = next((it for it in items if it["prompt"] == pid and it["lines"] == row["lines"]), None)
            if same:
                same["configs"].append(f"{system}-{config}")
            else:
                items.append({"prompt": pid, "configs": [f"{system}-{config}"], "lines": row["lines"],
                              "traits": row["traits"], "intensity": row["intensity"], "category": row["category"],
                              "metrics": row["metrics"]})
    for n, it in zip(rng.sample(range(1, len(items) + 1), len(items)), items):
        it["item"] = n
    items.sort(key=lambda it: it["item"])

    spare = [pid for pid in by_cat["single"] if pid not in selected]       # practice: prompts not rated
    a, b = rng.sample(spare, 2)
    practice = {"prompt": a, "request": f"Request: {request_text(prompts[a]['traits'])}\nIntensity: "
                                        f"{prompts[a]['intensity']}",
                "poems": [rows[("D", "full", a)]["lines"], rows[("A", "base", a)]["lines"]]}
    return selected, items, practice, missing


def rater_layout(items, selected, rater, seed):
    """One rater's requests, in their own random order, split into PARTS parts; poems shuffled within a request."""
    rng = random.Random(f"{seed}-rater-{rater}")
    order = rng.sample(selected, len(selected))
    reqs = []
    for pid in order:
        poems = [it for it in items if it["prompt"] == pid]
        rng.shuffle(poems)
        reqs.append({"request": request_text(poems[0]["traits"]), "intensity": poems[0]["intensity"],
                     "poems": [{"title": f"Poem #{it['item']:03d}", "lines": it["lines"]} for it in poems]})
    size = -(-len(reqs) // PARTS)
    return [reqs[i:i + size] for i in range(0, len(reqs), size)]


def cmd_forms(args):
    seed = load_config()["seed"]
    if not CHOSEN.exists():
        sys.exit(f"{CHOSEN} missing: run `python -m eval.run_auto_eval analyse` first")
    if (DIR / "responses").exists() and any((DIR / "responses").glob("rater_*.csv")) and not args.force:
        sys.exit(f"{DIR / 'responses'} already has responses; rebuilding would change the key. Pass --force to redo.")
    selected, items, practice, missing = build_items(read_jsonl(CHOSEN), seed)
    if missing:
        print(f"note: no poem for {missing}; those are left out")
    data = {"title": TITLE, "intro": INTRO, "guide": GUIDE, "criteria": CRITERIA,
            "raters": [{"rater": k, "practice": practice, "parts": rater_layout(items, selected, k, seed)}
                       for k in range(1, args.raters + 1)]}
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "items.jsonl").write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in items), encoding="utf-8")
    # json.dumps makes DATA a JavaScript literal (poems can't break out of it), and ASCII-only escaping also covers
    # the two line-separator characters older JavaScript rejected inside strings
    runners = "\n".join(f"function buildRater{k}() {{ buildRater_({k}); }}" for k in range(1, args.raters + 1))
    script = SCRIPT.replace("__RUNNERS__", runners).replace("__DATA__", json.dumps(data, ensure_ascii=True, indent=1))
    (DIR / "build_forms.gs").write_text(script, encoding="utf-8")
    (DIR / "HOW_TO_RATE.txt").write_text(INTRO + "\n\n" + GUIDE + "\n", encoding="utf-8")
    (DIR / "meta.json").write_text(json.dumps({"poem_seed": POEM_SEED, "selection_seed": seed, "prompts": selected,
                                               "mix": MIX, "configs": [f"{s}-{c}" for s, c in CONFIGS],
                                               "items": len(items), "raters": args.raters, "missing": missing},
                                              indent=2) + "\n", encoding="utf-8")
    shared = sum(len(it["configs"]) > 1 for it in items)
    print(f"{len(selected)} prompts, {len(items)} poems ({shared} shared by two configurations), {args.raters} raters")
    print(f"wrote {DIR / 'build_forms.gs'} (paste into script.google.com), items.jsonl (the key), HOW_TO_RATE.txt")


def read_responses(path):
    """({item: {criterion: rating}} from the last response in one form's responses CSV, the number of responses). A
    rating that is not a whole number is left out, and reported as missing by read_rater."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    got = defaultdict(dict)
    for column, value in (rows[-1].items() if rows else []):
        match = TITLE_RE.match(column or "")
        if match:
            try:
                got[int(match.group(1))][match.group(2)] = int(value)
            except (TypeError, ValueError):
                pass
    return got, len(rows)


def read_rater(paths, items, use_last=False):
    """One rater's ratings, merged over their part files (rater_<k>_part<p>.csv), and the problems: a part missing,
    a part answered more than once (a resubmission, or someone else with the link: check the timestamps, then
    use_last keeps the latest), or a poem or criterion not rated 1-5."""
    got, problems = {}, []
    parts = {int(re.search(r"_part(\d+)$", p.stem).group(1)) for p in paths}
    if parts != set(range(1, PARTS + 1)):
        problems.append(f"{paths[0].stem.split('_part')[0]}: parts {sorted(parts)} found, {PARTS} expected")
    for path in paths:
        ratings, n = read_responses(path)
        got.update(ratings)
        if n > 1 and not use_last:
            problems.append(f"{path.name}: {n} responses (check the timestamps; --use-last keeps the latest)")
    for it in items:
        for c in CRITERIA:
            if got.get(it["item"], {}).get(c) not in (1, 2, 3, 4, 5):
                problems.append(f"{paths[0].stem.split('_part')[0]} poem #{it['item']:03d} {c}: missing or not 1-5")
    return got, problems


def cmd_collect(args):
    from scipy.stats import spearmanr
    items = {it["item"]: it for it in read_jsonl(DIR / "items.jsonl")}
    by_rater = defaultdict(list)
    for path in sorted((DIR / "responses").glob("rater_*_part*.csv")):
        by_rater[path.stem.split("_part")[0]].append(path)
    if len(by_rater) < 2:
        sys.exit(f"found {len(by_rater)} raters in {DIR / 'responses'}; agreement needs at least two")
    ratings, problems = {}, []
    for rater, paths in sorted(by_rater.items()):
        ratings[rater], bad = read_rater(paths, list(items.values()), args.use_last)
        problems += bad
    if problems:
        sys.exit(f"{len(problems)} problems, e.g. {problems[:10]}")

    flat = {r: [c for c in CRITERIA if statistics.pstdev([g[i][c] for i in items]) < 0.5] for r, g in ratings.items()}
    mean_item = {i: {c: statistics.mean(g[i][c] for g in ratings.values()) for c in CRITERIA} for i in items}
    per_prompt = defaultdict(lambda: defaultdict(dict))         # config -> criterion -> prompt -> mean rating
    for i, it in items.items():
        for config in it["configs"]:
            for c in CRITERIA:
                per_prompt[config][c][it["prompt"]] = mean_item[i][c]
    heldout = {it["prompt"] for it in items.values() if it["category"] == "heldout"}

    results = {}
    for config in [f"{s}-{c}" for s, c in CONFIGS]:
        results[config] = {c: {**M.bootstrap_ci(list(per_prompt[config][c].values()), args.bootstrap),
                               "heldout": M.mean([v for p, v in per_prompt[config][c].items() if p in heldout])}
                           for c in CRITERIA}
    agreement = {c: M.krippendorff_alpha([[g[i][c] for g in ratings.values()] for i in items]) for c in CRITERIA}
    tests = [(a, b, c, M.paired(per_prompt[a][c], per_prompt[b][c], args.bootstrap))
             for a, b in COMPARISONS for c in CRITERIA]
    for (a, b, c, r), p in zip(tests, M.holm([r["p_wilcoxon"] for *_, r in tests])):
        r["p_holm"] = p
    automatic = {}
    for metric, criterion in AUTOMATIC:
        pairs = [(it["metrics"].get(metric), mean_item[i][criterion]) for i, it in items.items()
                 if it["metrics"].get(metric) is not None]
        if len(pairs) > 2:
            rho, p = spearmanr(*zip(*pairs))
            automatic[f"{metric} ~ {criterion}"] = {"spearman": float(rho), "p": float(p), "n": len(pairs)}

    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {"raters": list(ratings), "items": len(items), "flat_raters": {r: c for r, c in flat.items() if c},
               "results": results, "agreement_alpha_ordinal": agreement,
               "comparisons": {f"{a} vs {b}": {} for a, b in COMPARISONS}, "automatic_vs_human": automatic}
    for a, b, c, r in tests:
        summary["comparisons"][f"{a} vs {b}"][c] = r
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"{len(ratings)} raters, {len(items)} poems" + (f" | flat raters: {summary['flat_raters']}" if any(flat.values()) else ""))
    print(f"\n{'':10}" + "".join(f"{c[:9]:>11}" for c in CRITERIA))
    for config, res in results.items():
        print(f"{config:10}" + "".join(f"{res[c]['mean']:>11.2f}" for c in CRITERIA))
    print(f"{'alpha':10}" + "".join(f"{agreement[c]:>11.2f}" for c in CRITERIA))
    for a, b, c, r in tests:
        if r["p_holm"] is not None and r["p_holm"] < 0.05:
            print(f"{a} vs {b}, {c}: {r['mean']:+.2f} (Holm p = {r['p_holm']:.3f})")
    print(f"wrote {RESULTS / 'summary.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("forms")
    f.add_argument("--raters", type=int, default=5)
    f.add_argument("--force", action="store_true", help="rebuild even though responses exist")
    c = sub.add_parser("collect")
    c.add_argument("--bootstrap", type=int, default=2000)
    c.add_argument("--use-last", action="store_true", help="a part answered more than once: keep the latest response")
    args = parser.parse_args()
    {"forms": cmd_forms, "collect": cmd_collect}[args.cmd](args)


if __name__ == "__main__":
    main()
