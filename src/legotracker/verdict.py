"""The one rule.

Where does today's price sit between the cheapest and dearest this set
is known to have been?

    top    = MRP, or the Amazon high if that is higher
    bottom = the Amazon low, or our cheapest recorded -- whichever is
             lower. Our own low only counts once we have enough days of
             history; on day one it is just today's price, which would
             collapse the range to nothing.

With no bottom anchor at all we fall back to plain percent off MRP.
"""
from .models import Verdict

ALERTABLE = {"BUY_NOW", "GOOD"}


def _money(value: float) -> str:
    return f"Rs{value:,.0f}"


def _present(values) -> list[float]:
    """Keep anchors that exist. 0.0 is a real anchor, not an absence."""
    return [v for v in values if v is not None]


def judge(price: float, mrp: float | None, amazon_low: float | None,
          amazon_high: float | None, recorded_low: float | None,
          history_days: int, in_stock: bool, stale: bool,
          thresholds: dict) -> Verdict:
    if not in_stock:
        return Verdict("WAIT", None, "out of stock", False)

    tops = [v for v in _present((mrp, amazon_high)) if v > 0]
    top = max(tops) if tops else None

    bottom_candidates = [amazon_low]
    if history_days >= thresholds["min_history_days"]:
        bottom_candidates.append(recorded_low)
    bottoms = _present(bottom_candidates)
    bottom = min(bottoms) if bottoms else None

    # No range to speak of: fall back to percent off MRP.
    if bottom is None or top is None or top <= 0:
        if not mrp or mrp <= 0:
            return Verdict("WAIT", None, "no price history yet", False)
        off = (mrp - price) / mrp * 100
        label = ("GOOD" if off >= thresholds["mrp_fallback_discount_pct"]
                 else "WAIT")
        return Verdict(label, None,
                       f"{off:.0f}% off MRP (no price history yet)",
                       label in ALERTABLE and not stale)

    span = top - bottom
    if span < thresholds["narrow_range_pct"] / 100 * top:
        # A set that never discounts is not news -- unless it finally
        # does. Breaking below its known floor is the most newsworthy
        # thing such a set can do, so it must not be swallowed here.
        if price < bottom:
            return Verdict(
                "BUY_NOW", 0.0,
                f"first real drop we have seen -- this set had never gone "
                f"below {_money(bottom)}", True)
        return Verdict(
            "NEVER_DISCOUNTS", None,
            f"price barely moves -- its whole range is only "
            f"{span / top * 100:.0f}% wide", False)

    position = (price - bottom) / span * 100
    if position <= thresholds["buy_now_pct"]:
        label = "BUY_NOW"
    elif position <= thresholds["good_pct"]:
        label = "GOOD"
    elif position < thresholds["fair_pct"]:
        label = "FAIR"
    else:
        label = "WAIT"

    # Old figures may make us more cautious, never less.
    if stale and label in ALERTABLE:
        label = "FAIR"

    reason = (f"{position:.0f}% up its range "
              f"({_money(bottom)}-{_money(top)})")
    if stale:
        reason += " -- figures are over 6 months old"

    return Verdict(label, position, reason, label in ALERTABLE)
