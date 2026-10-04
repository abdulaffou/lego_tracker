"""Loading of config.yaml and watchlist.yaml."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str = "config.yaml") -> dict:
    with open(ROOT / path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_watchlist(path: str = "watchlist.yaml") -> list[dict]:
    with open(ROOT / path, encoding="utf-8") as fh:
        entries = yaml.safe_load(fh)
    for entry in entries:
        entry["set"] = str(entry["set"])
    return entries
