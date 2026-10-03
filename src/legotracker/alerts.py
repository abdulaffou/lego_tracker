"""Deciding what is worth an email.

A tool that emails the same "lowest price!" every day gets ignored
within a fortnight. So we remember what we last said about each set and
speak only on real news.
"""
import json
from datetime import date
from pathlib import Path

from .models import Verdict


def load_state(path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path, state: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)


def _days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


RANK = {"WAIT": 0, "NEVER_DISCOUNTS": 0, "FAIR": 1, "GOOD": 2, "BUY_NOW": 3}


def is_news(set_number: str, verdict: Verdict, price: float, state: dict,
            today: str, cooldown_days: int) -> bool:
    if not verdict.alertable:
        return False
    last = state.get(set_number)
    if last is None:
        return True
    if price < last["price"]:
        return True                                   # a new low
    if RANK[verdict.label] > RANK.get(last["label"], 0):
        return True                                   # verdict improved
    return _days_between(last["date"], today) >= cooldown_days


def record_alert(state: dict, set_number: str, verdict: Verdict,
                 price: float, today: str) -> None:
    state[set_number] = {"label": verdict.label, "price": price,
                         "date": today}


def is_absurd(price: float, previous_price: float | None,
              swing_pct: float) -> bool:
    """A price that moved more than swing_pct overnight is probably a glitch."""
    if not previous_price:
        return False
    return abs(price - previous_price) / previous_price * 100 > swing_pct
