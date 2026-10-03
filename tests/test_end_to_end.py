import json

from legotracker.cli import build_report
from legotracker.config import load_config, load_watchlist
from legotracker.shops.shopify import parse_products

TODAY = "2026-10-04"
T = load_config()["thresholds"]

SHOPS = [("official", "official_products.json", "https://lego.mybrickhouse.com"),
         ("toycra", "toycra_products.json", "https://toycra.com"),
         ("funcorp", "funcorp_products.json", "https://www.funcorp.in")]


def todays_rows():
    rows = []
    for shop, fixture, base in SHOPS:
        payload = json.load(open(f"tests/fixtures/{fixture}"))
        rows += parse_products(payload, shop, base, TODAY)
    return rows


def verdicts(watchlist):
    _, every = build_report(todays_rows(), watchlist, [], TODAY, T)
    return {i["set_number"]: i["verdict"].label for i in every}


def test_day_one_verdicts_match_the_spec():
    assert verdicts(load_watchlist()) == {
        "10294": "GOOD",             # Titanic, near its floor
        "42172": "FAIR",             # McLaren, mid-range
        "10316": "WAIT",             # Rivendell, 60% up its range
        "10350": "WAIT",             # Tudor Corner, at its peak
        "76269": "WAIT",             # Avengers Tower, at its peak
        "11389": "NEVER_DISCOUNTS",  # flat all year
        "11371": "NEVER_DISCOUNTS",  # range only 6% wide
        "11377": "WAIT",             # no history at all
    }


def test_the_first_email_contains_exactly_titanic():
    alerts, _ = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    assert [a["set_number"] for a in alerts] == ["10294"]


def test_rivendell_is_never_recommended_on_day_one():
    # If this fails the range maths is inverted and the tool is
    # recommending the worst prices of the year.
    alerts, _ = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    assert "10316" not in {a["set_number"] for a in alerts}
    assert "76269" not in {a["set_number"] for a in alerts}


def test_without_amazon_figures_the_mrp_fallback_takes_over():
    stripped = []
    for entry in load_watchlist():
        stripped.append({k: v for k, v in entry.items()
                         if k not in ("amazon_low", "amazon_high", "seen_on")})
    labels = verdicts(stripped)
    assert labels["42172"] == "GOOD"   # 29% off MRP
    assert labels["10316"] == "GOOD"   # 20% off MRP
    assert labels["10294"] == "WAIT"   # 0% off, now invisible


def test_no_balloon_ever_reaches_a_verdict():
    _, every = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    for entry in every:
        assert entry["price"] > 1000, f"{entry['set_number']} at {entry['price']}"


def test_each_watchlist_set_appears_at_most_once():
    _, every = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    numbers = [e["set_number"] for e in every]
    assert len(numbers) == len(set(numbers))


def test_cheapest_shop_wins_for_the_mclaren():
    _, every = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    mclaren = next(e for e in every if e["set_number"] == "42172")
    assert mclaren["price"] == 29399.0
    assert mclaren["shop"] == "toycra"
