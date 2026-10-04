"""The append-only price record.

One CSV, committed after every run. Plain text, opens in Excel,
readable in ten years. Rows are only ever added.
"""
import csv
from pathlib import Path

from .models import PriceRow

FIELDS = ["date", "shop", "set_number", "price", "mrp",
          "in_stock", "url", "source", "suspect"]


def _as_record(row: PriceRow) -> dict:
    return {
        "date": row.date,
        "shop": row.shop,
        "set_number": row.set_number,
        "price": f"{row.price:.2f}",
        "mrp": "" if row.mrp is None else f"{row.mrp:.2f}",
        "in_stock": "true" if row.in_stock else "false",
        "url": row.url,
        "source": row.source,
        "suspect": "true" if row.suspect else "false",
    }


def _key(row: PriceRow) -> tuple:
    return (row.date, row.shop, row.set_number)


def append_rows(path, rows: list[PriceRow]) -> None:
    """Add today's rows.

    One row per (date, shop, set). Re-running on the same day -- the
    scheduled run plus a local `make check` -- replaces that day's rows
    rather than stacking a second copy, so the file stays one honest
    reading per shop per day.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    replacing = {_key(r) for r in rows}
    all_rows = read_rows(path)
    kept = [r for r in all_rows if _key(r) not in replacing]
    if len(kept) != len(all_rows):      # a same-day re-run superseded some
        _write(path, kept + list(rows))
        return

    new_file = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow(_as_record(row))


def _write(path, rows: list[PriceRow]) -> None:
    """Rewrite the whole file. Used only to replace a same-day re-run."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(_as_record(row))


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
                    # older files predate the column
                    suspect=record.get("suspect") == "true",
                ))
            except (KeyError, ValueError):
                continue  # a corrupt line must not sink the whole history
    return out


def _for_set(rows: list[PriceRow], set_number: str) -> list[PriceRow]:
    """Rows we trust for this set. Suspect rows are kept on disk for
    the record but never feed a verdict."""
    return [r for r in rows if r.set_number == set_number
            and not r.suspect]


def sticky_mrp(rows: list[PriceRow], set_number: str) -> float | None:
    """Highest list price ever seen; falls back to the highest price seen.

    Sticky so a shop briefly marking a set UP cannot later make the
    return to normal look like a discount.
    """
    mine = _for_set(rows, set_number)
    if not mine:
        return None
    # A list price scraped off a page can be any number on that page.
    # Prefer the shops' own feeds whenever we have one.
    feed_listed = [r.mrp for r in mine
                   if r.mrp is not None and r.mrp > 0 and r.source == "feed"]
    if feed_listed:
        return max(feed_listed)
    listed = [r.mrp for r in mine if r.mrp is not None and r.mrp > 0]
    return max(listed) if listed else max(r.price for r in mine)


def recorded_low(rows: list[PriceRow], set_number: str) -> float | None:
    """Cheapest in-stock price we have ever recorded for this set."""
    prices = [r.price for r in _for_set(rows, set_number) if r.in_stock]
    return min(prices) if prices else None


def history_days(rows: list[PriceRow], set_number: str) -> int:
    """How many distinct days we have data for."""
    return len({r.date for r in _for_set(rows, set_number)})


def latest_price(rows: list[PriceRow], set_number: str) -> float | None:
    """Cheapest trusted price on the most recent day we have for this set.

    This is what a new price is judged implausible against -- NOT the
    all-time low. A set that genuinely hit its floor once must not make
    every later full-price day look like a huge swing.
    """
    mine = _for_set(rows, set_number)
    if not mine:
        return None
    newest = max(r.date for r in mine)
    return min(r.price for r in mine if r.date == newest)


def year_path(base, today: str) -> Path:
    """data/prices.csv + "2026-10-04" -> data/prices-2026.csv

    One file per year. The run records the whole catalogue daily so the
    retirement signal has data to work with, which is ~240KB a day --
    a single file would cross GitHub's 100MB limit inside two years.
    """
    base = Path(base)
    return base.with_name(f"{base.stem}-{today[:4]}{base.suffix}")


def read_all(base) -> list[PriceRow]:
    """Every year file, plus any legacy un-suffixed file."""
    base = Path(base)
    paths = sorted(base.parent.glob(f"{base.stem}-*{base.suffix}")) \
        if base.parent.exists() else []
    if base.exists():
        paths.insert(0, base)
    rows: list[PriceRow] = []
    for path in paths:
        rows.extend(read_rows(path))
    return rows
