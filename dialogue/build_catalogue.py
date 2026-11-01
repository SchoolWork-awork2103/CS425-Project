"""Run `python -m dialogue.build_catalogue` after editing traits or training data."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from .catalogue import ROOT, TraitCatalogue


def build(traits_path=ROOT / "data/traits.json", train_path=ROOT / "data/disses/corpus/train.jsonl"):
    sources = {"traits": Path(traits_path), "poem_train": Path(train_path)}
    traits = json.loads(sources["traits"].read_text(encoding="utf-8"))
    counts, aliases = Counter(), defaultdict(set)
    for line in sources["poem_train"].read_text(encoding="utf-8").splitlines():
        for key in set(json.loads(line)["traits"]):
            if key not in traits:
                raise ValueError(f"Unknown training trait: {key}")
            counts[key] += 1
    entries = []
    for key, info in sorted(traits.items()):
        if info["heldout"] == (counts[key] > 0):
            raise ValueError(f"Held-out flag disagrees with training membership: {key}")
        for alias in [key, *info["synonyms"]]:
            aliases[" ".join(alias.casefold().split())].add(key)
        entries.append({"key": key, "description": info["description"], "synonyms": info["synonyms"],
                        "seen_in_poem_training": counts[key] > 0, "poem_training_count": counts[key]})
    data = {"schema_version": 1,
            "source_sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in sources.items()},
            "ambiguous_aliases": {a: sorted(v) for a, v in sorted(aliases.items()) if len(v) > 1},
            "entries": entries}
    TraitCatalogue(data)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/trait_catalogue.json")
    args = parser.parse_args()
    data = build()
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(data['entries'])} traits; ambiguous aliases: {data['ambiguous_aliases']}")


if __name__ == "__main__":
    main()
