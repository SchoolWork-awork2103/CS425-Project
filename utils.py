import os, random
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent


def load_config(path=ROOT / "config.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def project_path(rel):
    return ROOT / rel


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
