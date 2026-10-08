import pytest

from legotracker.config import load_config
from legotracker.verdict import judge

T = load_config()["thresholds"]


def j(price, mrp, lo=None, hi=None, rec=None, days=0, stock=True, stale=False):
    return judge(price=price, mrp=mrp, amazon_low=lo, amazon_high=hi,
                 recorded_low=rec, history_days=days, in_stock=stock,
                 stale=stale, thresholds=T)


# --- the eight real sets, day one (spec section 12) -----------------

@pytest.mark.parametrize("set_number,price,mrp,lo,hi,expected", [
    ("11389", 11999, 11999, 11999, 11999, "NEVER_DISCOUNTS"),
    ("10294", 63999, 63999, 57000, 98999, "GOOD"),
    ("11377", 69999, 69999, None,  None,  "WAIT"),
    ("10350", 24499, 24499, 14500, 24501, "WAIT"),
    ("11371", 24999, 24999, 24479, 25999, "NEVER_DISCOUNTS"),
    ("76269", 48999, 48999, 24501, 48021, "WAIT"),
    ("42172", 29399, 41199, 20600, 40490, "FAIR"),
    ("10316", 40399, 50399, 25200, 45392, "WAIT"),
])
def test_day_one_verdicts(set_number, price, mrp, lo, hi, expected):
    assert j(price, mrp, lo, hi, rec=price, days=0).label == expected


def test_only_titanic_is_alertable_on_day_one():
    sets = [("11389", 11999, 11999, 11999, 11999),
            ("10294", 63999, 63999, 57000, 98999),
            ("11377", 69999, 69999, None, None),
            ("10350", 24499, 24499, 14500, 24501),
            ("11371", 24999, 24999, 24479, 25999),
            ("76269", 48999, 48999, 24501, 48021),
            ("42172", 29399, 41199, 20600, 40490),
            ("10316", 40399, 50399, 25200, 45392)]
    alertable = [s for s, p, m, lo, hi in sets
                 if j(p, m, lo, hi, rec=p, days=0).alertable]
    assert alertable == ["10294"]


# --- the MRP fallback, with every Amazon figure removed -------------

def test_fallback_flags_mclaren_and_rivendell():
    assert j(29399, 41199, rec=29399, days=0).label == "GOOD"   # 29% off
    assert j(40399, 50399, rec=40399, days=0).label == "GOOD"   # 20% off


def test_fallback_is_quiet_at_full_price():
    assert j(63999, 63999, rec=63999, days=0).label == "WAIT"


def test_fallback_boundary_at_exactly_fifteen_percent():
    assert j(8500, 10000, rec=8500, days=0).label == "GOOD"     # exactly 15%
    assert j(8501, 10000, rec=8501, days=0).label == "WAIT"     # just under


# --- Review Focus item 2: degenerate ranges -------------------------

def test_equal_anchors_do_not_divide_by_zero():
    assert j(100, 100, lo=100, hi=100).label == "NEVER_DISCOUNTS"


def test_price_above_the_high_anchor_is_wait_not_a_bargain():
    v = j(60000, 48999, lo=24501, hi=48021)
    assert v.label == "WAIT"
    assert v.position > 100


def test_price_below_the_low_anchor_is_buy_now():
    v = j(20000, 41199, lo=20600, hi=40490)
    assert v.label == "BUY_NOW"
    assert v.position < 0


def test_a_new_low_says_so_instead_of_minus_percent():
    # Amazon's McLaren on 2026-10-08: Rs1 under the old low read as
    # "-0% up its range".
    v = j(20599, 41199, lo=20600, hi=40490)
    assert v.reason == "lowest price yet -- under the old low of Rs20,600"


# --- Review Focus item 3: missing MRP -------------------------------

def test_missing_mrp_uses_the_amazon_high_as_the_top():
    assert j(26000, None, lo=20600, hi=40490).label == "FAIR"


def test_missing_mrp_and_no_amazon_data_is_unknown_not_a_crash():
    v = j(26000, None, lo=None, hi=None)
    assert v.label == "WAIT"
    assert v.alertable is False


# --- band boundaries ------------------------------------------------

def test_band_boundaries_are_inclusive_at_the_top():
    # range 0..10000 so position equals price/100
    assert j(1000, 10000, lo=0, hi=10000).label == "BUY_NOW"   # exactly 10%
    assert j(1001, 10000, lo=0, hi=10000).label == "GOOD"
    assert j(2500, 10000, lo=0, hi=10000).label == "GOOD"      # exactly 25%
    assert j(2501, 10000, lo=0, hi=10000).label == "FAIR"
    assert j(4999, 10000, lo=0, hi=10000).label == "FAIR"
    assert j(5000, 10000, lo=0, hi=10000).label == "WAIT"      # exactly 50%


# --- the rails ------------------------------------------------------

def test_out_of_stock_is_always_wait():
    v = j(20000, 41199, lo=20600, hi=40490, stock=False)
    assert v.label == "WAIT"
    assert "stock" in v.reason.lower()


def test_stale_figures_cannot_promote_only_demote():
    fresh = j(58000, 63999, lo=57000, hi=98999, stale=False)
    stale = j(58000, 63999, lo=57000, hi=98999, stale=True)
    assert fresh.label in ("BUY_NOW", "GOOD")
    assert stale.label == "FAIR"
    assert stale.alertable is False


def test_stale_figures_still_allow_a_wait():
    assert j(48999, 48999, lo=24501, hi=48021, stale=True).label == "WAIT"


def test_recorded_low_ignored_until_min_history_days():
    # 13 days: recorded low must not count, so this falls back to MRP
    assert j(50000, 100000, rec=10000, days=13).label == "GOOD"
    # 14 days: recorded low becomes the bottom anchor -> middling
    assert j(50000, 100000, rec=10000, days=14).label == "FAIR"


def test_reason_names_the_numbers_used():
    v = j(63999, 63999, lo=57000, hi=98999)
    assert "57,000" in v.reason and "98,999" in v.reason


def test_only_buy_now_and_good_are_alertable():
    assert j(1000, 10000, lo=0, hi=10000).alertable is True    # BUY_NOW
    assert j(2000, 10000, lo=0, hi=10000).alertable is True    # GOOD
    assert j(3000, 10000, lo=0, hi=10000).alertable is False   # FAIR
    assert j(9000, 10000, lo=0, hi=10000).alertable is False   # WAIT
