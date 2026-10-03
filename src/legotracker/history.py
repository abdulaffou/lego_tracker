"""The append-only price record.

One CSV, committed after every run. Plain text, opens in Excel,
readable in ten years. Rows are only ever added.
"""
import csv
from pathlib import Path

from .models import PriceRow

FIELDS = ["date", "shop", "set_number", "price", "mrp",
          "in_stock", "url", "source"]


def append_rows(path, rows: list[PriceRow]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow({
                "date": row.date,
                "shop": row.shop,
                "set_number": row.set_number,
                "price": f"{row.price:.2f}",
                "mrp": "" if row.mrp is None else f"{row.mrp:.2f}",
                "in_stock": "true" if row.in_stock else "false",
                "url": row.url,
                "source": row.source,
            })


def read_rows(path) -> list[PriceRow]:
    path = Path(path)
    if not path.exists():
        return []
    out: list[PriceRow] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for record in csv.DictReader(fh):
            try:
                out.append(PriceRow(
                    date=record["date"],
                    shop=record["shop"],
                    set_number=record["set_number"],
                    price=float(record["price"]),
                    mrp=float(record["mrp"]) if record["mrp"] else None,
                    in_stock=record["in_stock"] == "true",
                    url=record["url"],
                    source=record["source"],
                ))
            except (KeyError, ValueError):
                continue  # a corrupt line must not sink the whole history
    return out


def _for_set(rows: list[PriceRow], set_number: str) -> list[PriceRow]:
    return [r for r in rows if r.set_number == set_number]


def sticky_mrp(rows: list[PriceRow], set_number: str) -> float | None:
    """Highest list price ever seen; falls back to the highest price seen.

    Sticky so a shop briefly marking a set UP cannot later make the
    return to normal look like a discount.
    """
    mine = _for_set(rows, set_number)
    if not mine:
        return None
    listed = [r.mrp for r in mine if r.mrp is not None]
    return max(listed) if listed else max(r.price for r in mine)


def recorded_low(rows: list[PriceRow], set_number: str) -> float | None:
    """Cheapest in-stock price we have ever recorded for this set."""
    prices = [r.price for r in _for_set(rows, set_number) if r.in_stock]
    return min(prices) if prices else None


def history_days(rows: list[PriceRow], set_number: str) -> int:
    """How many distinct days we have data for."""
    return len({r.date for r in _for_set(rows, set_number)})
