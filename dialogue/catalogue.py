"""The catalogue is small enough to include in full in every interpretation prompt."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TraitCatalogue:
    def __init__(self, data):
        if data.get("schema_version") != 1 or type(data.get("entries")) is not list:
            raise ValueError("Unsupported trait catalogue schema; rebuild the catalogue")
        self.data = data
        self.entries = {}
        for entry in data["entries"]:
            key = entry.get("key")
            if not isinstance(key, str) or not key or key in self.entries:
                raise ValueError("Duplicate or invalid catalogue key")
            if not isinstance(entry.get("description"), str) or not entry["description"].strip():
                raise ValueError(f"Missing neutral description: {key}")
            if type(entry.get("synonyms")) is not list or any(type(s) is not str for s in entry["synonyms"]):
                raise ValueError(f"Invalid synonyms: {key}")
            count = entry.get("poem_training_count")
            if type(count) is not int or count < 0 or type(entry.get("seen_in_poem_training")) is not bool:
                raise ValueError(f"Invalid training metadata: {key}")
            if entry["seen_in_poem_training"] != (count > 0):
                raise ValueError(f"Inconsistent training metadata: {key}")
            self.entries[key] = entry
        if not self.entries:
            raise ValueError("Empty trait catalogue")
        self.keys = frozenset(self.entries)
        self.prompt = "\n".join(
            f"{k}: {e['description']} Synonyms: {', '.join(e['synonyms'])}."
            for k, e in self.entries.items())
        self.fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @classmethod
    def load(cls, path=None):
        return cls(json.loads(Path(path or ROOT / "data/trait_catalogue.json").read_text(encoding="utf-8")))
