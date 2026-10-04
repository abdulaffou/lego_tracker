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
    suspect: bool = False  # implausible; recorded, flagged, never trusted
    # Display only -- shown in the email, never written to prices.csv.
    # They describe the set, not the day, so they do not belong in history.
    image: str | None = None
    pieces: int | None = None


@dataclass(frozen=True)
class Verdict:
    """What the tool thinks of today's price, and why."""
    label: str                 # BUY_NOW GOOD FAIR WAIT NEVER_DISCOUNTS
    position: float | None     # % of the way up the known range
    reason: str                # plain-language, goes straight into the email
    alertable: bool            # whether this is worth an email
    # The two ends of the range the position was measured against, so the
    # email can draw the bar without recomputing them.
    low: float | None = None
    high: float | None = None
