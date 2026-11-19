import os, random, re, unicodedata
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent


def load_config(path=ROOT / "config.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_path(rel):
    return ROOT / rel


# Shared by the quatrain corpus and the diss data, so both reach the tokenizer in the same form.
PUNCT_MAP = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                           "—": " - ", "–": " - ", "…": "...", "*": ""})


def normalize_text(text):
    """Lowercase, straight quotes, spaced dashes, no markdown asterisks, accents folded (café -> cafe)."""
    text = unicodedata.normalize("NFKD", text.translate(PUNCT_MAP))
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+-$", "", text)            # a dash left dangling at the end of a line
    return text.lower()


def set_seed(seed=None):
    if seed is None:
        seed = load_config()["seed"]
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass
    return seed
