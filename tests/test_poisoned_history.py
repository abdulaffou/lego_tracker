"""Review finding C1: one bad row must not blind the tracker forever."""
from legotracker.alerts import is_absurd
from legotracker.cli import build_report, flag_suspect_rows
from legotracker.config import load_config
from legotracker.history import latest_price, recorded_low, sticky_mrp
from legotracker.models import PriceRow

T = load_config()["thresholds"]


def row(date="2026-10-04", shop="official", set_number="10294", price=63999.0,
        mrp=None, in_stock=True, url="https://x.test/p", source="feed",
        suspect=False):
    return PriceRow(date, shop, set_number, price, mrp, in_stock, url,
                    source, suspect)


WATCH = [{"set": "10294", "name": "Titanic",
          "amazon_low": 57000, "amazon_high": 98999}]


def test_absurd_compares_against_the_most_recent_price_not_the_all_time_low():
    # A set that genuinely hit Rs20,600 once must not make every later
    # full-price day look like a 100% swing.
    history = [row(date="2026-10-01", set_number="42172", price=20600.0),
               row(date="2026-10-02", set_number="42172", price=41199.0)]
    assert latest_price(history, "42172") == 41199.0
    assert is_absurd(41199.0, latest_price(history, "42172"), 70) is False


def test_an_implausible_row_is_flagged_rather_than_silently_dropped():
    # Spec section 11: "Record it, flag it, don't alert."
    # The flag's surface is the suspect column in prices.csv.
    history = [row(date="2026-10-03", price=63999.0)]
    today = [row(date="2026-10-04", shop="amazon", price=2999.0,
                 source="page")]
    flagged = flag_suspect_rows(today, history, T)
    assert flagged[0].suspect is True
    assert flagged[0].price == 2999.0, "the row is kept, not discarded"


def test_a_page_price_wildly_off_the_same_day_feeds_is_flagged_on_day_one():
    # The live Rs2,999 Titanic, caught with NO history at all.
    today = [row(shop="official", price=63999.0, source="feed"),
             row(shop="amazon", price=2999.0, source="page")]
    flagged = {r.shop: r for r in flag_suspect_rows(today, [], T)}
    assert flagged["amazon"].suspect is True
    assert flagged["official"].suspect is False


def test_a_genuine_cross_shop_discount_is_not_flagged():
    # McLaren: Rs29,399 Toycra against Rs41,199 official is real.
    today = [row(set_number="42172", shop="official", price=41199.0,
                 source="feed"),
             row(set_number="42172", shop="toycra", price=29399.0,
                 source="feed")]
    assert all(not r.suspect for r in flag_suspect_rows(today, [], T))


def test_a_suspect_row_never_becomes_the_recorded_low():
    rows = [row(price=63999.0), row(price=2999.0, suspect=True)]
    assert recorded_low(rows, "10294") == 63999.0


def test_a_suspect_row_never_becomes_the_sticky_mrp():
    rows = [row(mrp=63999.0), row(mrp=999999.0, suspect=True)]
    assert sticky_mrp(rows, "10294") == 63999.0


def test_the_set_still_gets_judged_the_day_after_a_bad_row():
    # The exact scenario that happened live: a bogus Rs2,999 Amazon row.
    # The next day's real price must still produce a verdict.
    history = [row(date="2026-10-03", price=63999.0),
               row(date="2026-10-03", shop="amazon", price=2999.0,
                   source="page", suspect=True)]
    today = [row(date="2026-10-04", price=63999.0)]
    _, every = build_report(today, WATCH, history, "2026-10-04", T)
    assert [e["set_number"] for e in every] == ["10294"]
    assert every[0]["verdict"].label == "GOOD"


def test_zero_recorded_low_does_not_disable_the_absurd_guard():
    # Minor 1: `if not previous_price` treats 0.0 as "nothing to compare".
    assert is_absurd(63999.0, 0.0, 70) is True


def test_absurd_guard_is_off_only_when_there_is_genuinely_no_previous():
    assert is_absurd(63999.0, None, 70) is False
