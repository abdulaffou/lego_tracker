"""Shared data shapes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceRow:
    """One shop's price for one set on one day."""
    date: str              # ISO YYYY-MM-DD
    shop: str
    set_number: str
    price: float
    mrp: float | None      # None when the shop publishes no list price
    in_stock: bool
    url: str
    source: str            # "feed" | "page" | "manual"


@dataclass(frozen=True)
class Verdict:
    """What the tool thinks of today's price, and why."""
    label: str                 # BUY_NOW GOOD FAIR WAIT NEVER_DISCOUNTS
    position: float | None     # % of the way up the known range
    reason: str                # plain-language, goes straight into the email
    alertable: bool            # whether this is worth an email
