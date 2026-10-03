"""Entry point: fetch, match, record, judge, alert."""
import argparse
import logging
import statistics
import sys
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

from .alerts import is_absurd, is_news, load_state, record_alert, save_state
from .config import load_config, load_watchlist
from .history import (append_rows, history_days, latest_price, read_all,
                      recorded_low, sticky_mrp, year_path)
from .mailer import compose, send
from .shops import fetch_all
from .shops.amazon import fetch_amazon, fetch_price_history
from .models import Verdict
from .verdict import judge
from .workbook import build_workbook

log = logging.getLogger(__name__)


def _is_stale(seen_on, today: str, stale_days: int) -> bool:
    if not seen_on:
        return False
    seen = seen_on if isinstance(seen_on, str) else seen_on.isoformat()
    try:
        delta = date.fromisoformat(today) - date.fromisoformat(seen)
    except ValueError:
        return False
    return delta.days > stale_days


def is_digest_day(today: str) -> bool:
    """Sunday. The weekly reassurance that the tool is still running."""
    return date.fromisoformat(today).weekday() == 6


def flag_suspect_rows(rows, history, thresholds):
    """Mark implausible rows instead of dropping them.

    Spec section 11: record it, flag it, do not alert on it. A flagged
    row still reaches prices.csv, but history.py refuses to let it
    become a low, an MRP, or the baseline for tomorrow's plausibility
    check -- so one bad row cannot blind the tracker to a set forever.

    Two ways a row is implausible:
      1. it moved more than absurd_swing_pct against the most recent
         trusted price for that set, or
      2. it is a scraped page price far from the same day's shop feeds.
         This is what catches a wrong price on day one, with no history
         at all -- the live Rs2,999 Titanic came from a recommended
         product on an unavailable listing.
    """
    band = thresholds["page_sanity_band_pct"] / 100
    out = []
    for set_number in {r.set_number for r in rows}:
        group = [r for r in rows if r.set_number == set_number]
        previous = latest_price(history, set_number)
        feeds = [r.price for r in group if r.source == "feed"]
        reference = statistics.median(feeds) if feeds else None
        for row in group:
            bad = is_absurd(row.price, previous,
                            thresholds["absurd_swing_pct"])
            if not bad and reference and row.source != "feed":
                if not (reference * (1 - band) <= row.price
                        <= reference * (1 + band)):
                    log.warning("%s price %s from %s is far from today's "
                                "feeds (%s); flagging as suspect",
                                set_number, row.price, row.shop, reference)
                    bad = True
            out.append(replace(row, suspect=True) if bad else row)
    return out


def build_report(rows, watchlist, history, today, thresholds):
    """Judge every watchlist set. Returns (alertable items, all items)."""
    all_items, alertable = [], []

    for entry in watchlist:
        set_number = entry["set"]
        todays = [r for r in rows
                  if r.set_number == set_number and not r.suspect]
        if not todays:
            continue   # no trustworthy price for this set today

        in_stock = [r for r in todays if r.in_stock]
        best = min(in_stock or todays, key=lambda r: r.price)

        combined = history + todays
        mrp = sticky_mrp(combined, set_number)
        previous = recorded_low(history, set_number)

        verdict = judge(
            price=best.price,
            mrp=mrp,
            amazon_low=entry.get("amazon_low"),
            amazon_high=entry.get("amazon_high"),
            recorded_low=previous,
            history_days=history_days(history, set_number),
            in_stock=bool(in_stock),
            stale=_is_stale(entry.get("seen_on"), today,
                            thresholds["stale_days"]),
            thresholds=thresholds,
        )

        item = {
            "set_number": set_number,
            "name": entry.get("name", set_number),
            "price": best.price,
            "shop": best.shop,
            "url": best.url,
            "verdict": verdict,
            "sources": len({r.shop for r in todays}),
            "history_days": history_days(history, set_number),
            "mrp": mrp,
            "in_stock": bool(in_stock),
        }
        all_items.append(item)
        if verdict.alertable:
            alertable.append(item)

    return alertable, all_items


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="LEGO price tracker")
    parser.add_argument("--local", action="store_true",
                        help="run from this machine (Amazon works here)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the email instead of sending it")
    args = parser.parse_args(argv)

    config = load_config()
    thresholds = config["thresholds"]
    watchlist = load_watchlist()
    today = datetime.now().date().isoformat()

    rows, failed = fetch_all(today)

    # Amazon and pricehistory.app: best effort, never fatal.
    for entry in watchlist:
        if entry.get("asin"):
            row = fetch_amazon(entry["asin"], entry["set"], today)
            if row:
                rows.append(row)
            elif args.local:
                failed.append(f"amazon:{entry['set']}")
        if entry.get("price_history_url"):
            stats = fetch_price_history(entry["price_history_url"])
            if stats:
                entry["amazon_low"] = stats["low"]
                entry["amazon_high"] = stats["high"]
                entry["seen_on"] = today

    history = read_all(config["paths"]["prices"])
    rows = flag_suspect_rows(rows, history, thresholds)
    alertable, every = build_report(rows, watchlist, history, today,
                                    thresholds)
    append_rows(year_path(config["paths"]["prices"], today), rows)

    state = load_state(config["paths"]["state"])
    news = [i for i in alertable
            if is_news(i["set_number"], i["verdict"], i["price"], state,
                       today, thresholds["cooldown_days"])]

    # A shop that has been down for weeks must not look like a quiet
    # day, but it must not mail daily either.
    if failed and not is_news("__shops__",
                              Verdict("GOOD", None, "shops failed", True),
                              0.0, state, today,
                              thresholds["cooldown_days"]):
        failed_for_email = []
    else:
        failed_for_email = failed

    # The spreadsheet is written every run, news or not, so it is always
    # there to open.
    book = Path(config["paths"]["prices"]).with_name("lego-prices.xlsx")
    build_workbook(book, every, history + rows, today)
    log.info("spreadsheet written to %s", book)

    digest = every if is_digest_day(today) else None
    subject, body = compose(news, failed_for_email, today, digest=digest)
    if subject is None:
        log.info("nothing worth an email today")
        return 0

    if args.dry_run:
        print(subject)
        print()
        print(body)
        print(f"\n[attachment: {book}]")
        return 0

    send(subject, body, config, attachment=book)
    if failed_for_email:
        record_alert(state, "__shops__",
                     Verdict("GOOD", None, "shops failed", True), 0.0, today)
    for item in news:
        record_alert(state, item["set_number"], item["verdict"],
                     item["price"], today)
    save_state(config["paths"]["state"], state)
    log.info("emailed about %s set(s)", len(news))
    return 0


if __name__ == "__main__":
    sys.exit(main())
