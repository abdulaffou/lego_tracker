"""Review findings C2, I1, I2, I3."""
import pytest

from legotracker.config import load_config
from legotracker.history import sticky_mrp
from legotracker.models import PriceRow
from legotracker.shops.amazon import parse_amazon_page
from legotracker.shops.shopify import parse_products
from legotracker.verdict import judge

T = load_config()["thresholds"]
TODAY = "2026-10-04"


def j(price, mrp, lo=None, hi=None, rec=None, days=0, stock=True, stale=False):
    return judge(price=price, mrp=mrp, amazon_low=lo, amazon_high=hi,
                 recorded_low=rec, history_days=days, in_stock=stock,
                 stale=stale, thresholds=T)


# --- C2: the MRP must be anchored like the price is ------------------

def test_mrp_from_a_distant_recommendation_block_is_not_used():
    html = ('<div class="a-price priceToPay">'
            '<span class="a-price-whole">69,999</span></div>'
            + "<div>filler</div>" * 500 +
            '<div class="rec-tile">M.R.P.: &#8377;99,999.00</div>')
    row = parse_amazon_page(html, "11377", "https://amzn.test/dp/X", TODAY)
    assert row.price == 69999.0
    assert row.mrp is None, "a far-away M.R.P. belongs to another product"


def test_an_mrp_implausibly_larger_than_the_price_is_rejected():
    html = ('<div class="a-price priceToPay">'
            '<span class="a-price-whole">2,999</span>'
            'M.R.P.: &#8377;99,999.00</div>')
    row = parse_amazon_page(html, "11377", "https://amzn.test/dp/X", TODAY)
    assert row.mrp is None, "a 33x list price is not a list price"


def test_a_scraped_mrp_never_outranks_a_feed_mrp():
    rows = [PriceRow(TODAY, "official", "11377", 69999.0, 69999.0, True,
                     "u", "feed"),
            PriceRow(TODAY, "amazon", "11377", 69999.0, 99999.0, True,
                     "u", "page")]
    assert sticky_mrp(rows, "11377") == 69999.0


# --- I1: a zero list price must never reach the arithmetic -----------

def test_zero_compare_at_price_parses_as_absent():
    payload = {"products": [{
        "title": "Minas Tirith", "vendor": "LEGO", "handle": "mt",
        "variants": [{"sku": "11377", "price": "69999.00",
                      "compare_at_price": "0.00", "available": True}]}]}
    assert parse_products(payload, "official", "https://x.test",
                          TODAY)[0].mrp is None


def test_zero_mrp_in_history_falls_back_to_the_highest_price():
    rows = [PriceRow(TODAY, "official", "11377", 69999.0, 0.0, True,
                     "u", "feed")]
    assert sticky_mrp(rows, "11377") == 69999.0


def test_zero_top_anchor_does_not_divide_by_zero():
    v = j(69999, 0.0, lo=None, hi=None, rec=69999, days=20)
    assert v.label in ("WAIT", "NEVER_DISCOUNTS")


# --- I2: a flat set that finally crashes must still be reported ------

def test_a_real_crash_on_a_never_discounting_set_is_still_news():
    # Project Hail Mary has been Rs11,999 every day for a year.
    # Dropping to Rs5,999 is the most newsworthy thing that could happen.
    v = j(5999, 11999, lo=11999, hi=11999, rec=11999, days=20)
    assert v.label == "BUY_NOW"
    assert v.alertable is True


def test_a_flat_set_at_its_usual_price_stays_quiet():
    v = j(11999, 11999, lo=11999, hi=11999, rec=11999, days=20)
    assert v.label == "NEVER_DISCOUNTS"
    assert v.alertable is False


# --- I3: other out-of-stock wordings --------------------------------

@pytest.mark.parametrize("phrase", [
    "Currently unavailable",
    "Temporarily out of stock",
    "Out of Stock",
])
def test_out_of_stock_wordings_yield_no_row(phrase):
    html = (f'<div id="availability">{phrase}</div>'
            '<div class="a-price priceToPay">'
            '<span class="a-price-whole">37,079</span></div>')
    assert parse_amazon_page(html, "42172", "https://amzn.test/dp/X",
                             TODAY) is None


def test_an_in_stock_page_still_parses():
    html = ('<div id="availability">In stock</div>'
            '<div class="a-price priceToPay">'
            '<span class="a-price-whole">37,079</span></div>')
    row = parse_amazon_page(html, "42172", "https://amzn.test/dp/X", TODAY)
    assert row.price == 37079.0
    assert row.in_stock is True
