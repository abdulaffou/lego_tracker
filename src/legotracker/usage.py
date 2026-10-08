"""Scrape.do request budget.

The free plan is 1,000 requests a month. Every request is counted in a
file that is committed with the price history, and a run never spends
past the cap in config.yaml or past what Scrape.do says is left (less a
reserve).
"""
import json
import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)

INFO_URL = "https://api.scrape.do/info"


def _month(today: str) -> str:
    return today[:7]


def load_usage(path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_usage(path, usage: dict) -> None:
    Path(path).write_text(json.dumps(usage, indent=2, sort_keys=True) + "\n")


def remaining_credits(token: str) -> int | None:
    """What Scrape.do says is left this month; None if it cannot say."""
    try:
        response = requests.get(INFO_URL, params={"token": token}, timeout=30)
        response.raise_for_status()
        return int(response.json()["RemainingMonthlyRequest"])
    except Exception as exc:
        # The exception text can carry the URL, and the URL the token.
        log.warning("scrape.do balance check failed: %s", type(exc).__name__)
        return None


def allowance(usage: dict, today: str, cap: int, remaining: int | None,
              reserve: int) -> int:
    """How many paid requests this run may make."""
    left = cap - usage.get(_month(today), {}).get("requests", 0)
    if remaining is not None:
        left = min(left, remaining - reserve)
    return max(0, left)


def record(usage: dict, today: str, spend: dict) -> None:
    month = usage.setdefault(_month(today), {"requests": 0, "credits": 0,
                                              "remaining": None, "days": {}})
    month["requests"] += 1
    month["credits"] += spend["credits"]
    if spend["remaining"] is not None:
        month["remaining"] = spend["remaining"]
    month["days"][today] = month["days"].get(today, 0) + 1


def summary(usage: dict, today: str, cap: int) -> str:
    month = usage.get(_month(today), {})
    text = (f"Scrape.do: {month.get('days', {}).get(today, 0)} requests "
            f"today, {month.get('requests', 0)} of {cap} this month")
    if month.get("remaining") is not None:
        text += f", {month['remaining']} credits left"
    return text
