"""Entry point: fetch, match, record, judge, alert."""
import argparse
import logging
import sys
from datetime import date, datetime

from .alerts import is_absurd, is_news, load_state, record_alert, save_state
from .config import load_config, load_watchlist
from .history import (append_rows, history_days, read_rows, recorded_low,
                      sticky_mrp)
from .mailer import compose, send
from .shops import fetch_all
from .shops.amazon import fetch_amazon, fetch_price_history
from .verdict import judge

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


def build_report(rows, watchlist, history, today, thresholds):
    """Judge every watchlist set. Returns (alertable items, all items)."""
    all_items, alertable = [], []

    for entry in watchlist:
        set_number = entry["set"]
        todays = [r for r in rows if r.set_number == set_number]
        if not todays:
            continue

        in_stock = [r for r in todays if r.in_stock]
        best = min(in_stock or todays, key=lambda r: r.price)

        combined = history + todays
        mrp = sticky_mrp(combined, set_number)
        previous = recorded_low(history, set_number)

        if is_absurd(best.price, previous, thresholds["absurd_swing_pct"]):
            log.warning("ignoring absurd price %s for %s", best.price,
                        set_number)
            continue

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

    history = read_rows(config["paths"]["prices"])
    alertable, _ = build_report(rows, watchlist, history, today, thresholds)
    append_rows(config["paths"]["prices"], rows)

    state = load_state(config["paths"]["state"])
    news = [i for i in alertable
            if is_news(i["set_number"], i["verdict"], i["price"], state,
                       today, thresholds["cooldown_days"])]

    subject, body = compose(news, failed, today)
    if subject is None:
        log.info("nothing worth an email today")
        return 0

    if args.dry_run:
        print(subject)
        print()
        print(body)
        return 0

    send(subject, body, config)
    for item in news:
        record_alert(state, item["set_number"], item["verdict"],
                     item["price"], today)
    save_state(config["paths"]["state"], state)
    log.info("emailed about %s set(s)", len(news))
    return 0


if __name__ == "__main__":
    sys.exit(main())
