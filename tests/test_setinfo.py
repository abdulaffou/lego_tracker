"""Set photos and piece counts, pulled from data we already download."""
import json

from legotracker.shops.shopify import parse_products

TODAY = "2026-10-04"


def only(payload, shop="official"):
    return parse_products(payload, shop, "https://x.test", TODAY)[0]


def test_image_url_is_captured():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "t",
        "images": [{"src": "https://cdn.test/10294_Prod.png"},
                   {"src": "https://cdn.test/10294_Box.jpg"}],
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": None, "available": True}]}]}
    assert only(payload).image == "https://cdn.test/10294_Prod.png"


def test_no_images_gives_none():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "t", "images": [],
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": None, "available": True}]}]}
    assert only(payload).image is None


def test_pieces_from_the_title():
    payload = {"products": [{
        "title": "Lego 42172 Technic McLaren P1 (3893 Pieces)",
        "vendor": "LEGO", "handle": "m",
        "variants": [{"sku": "Lego42172", "price": "29399.00",
                      "compare_at_price": None, "available": True}]}]}
    assert only(payload, "toycra").pieces == 3893


def test_pieces_from_the_description_when_the_title_is_bare():
    # The official store titles sets plainly but puts the count in the body.
    payload = {"products": [{
        "title": "Minas Tirith", "vendor": "LEGO", "handle": "mt",
        "body_html": "<p>A monumental build of <b>8,278 pieces</b>.</p>",
        "variants": [{"sku": "11377", "price": "69999.00",
                      "compare_at_price": None, "available": True}]}]}
    assert only(payload).pieces == 8278


def test_a_comma_grouped_count_parses():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "t",
        "body_html": "<p>9,090 pcs</p>",
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": None, "available": True}]}]}
    assert only(payload).pieces == 9090


def test_a_tiny_number_is_not_a_piece_count():
    # "3 pieces of advice" and similar must not become a piece count.
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "t",
        "body_html": "<p>Includes 3 pieces of display signage.</p>",
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": None, "available": True}]}]}
    assert only(payload).pieces is None


def test_pieces_absent_is_none_not_zero():
    payload = {"products": [{
        "title": "Tudor Corner", "vendor": "LEGO", "handle": "tc",
        "variants": [{"sku": "10350", "price": "24499.00",
                      "compare_at_price": None, "available": True}]}]}
    assert only(payload).pieces is None


def test_the_real_fixtures_yield_images_for_every_watchlist_set():
    watch = {"11389", "10294", "11377", "10350", "11371", "76269",
             "42172", "10316"}
    found = set()
    for fixture, shop in [("official_products.json", "official"),
                          ("toycra_products.json", "toycra")]:
        payload = json.load(open(f"tests/fixtures/{fixture}"))
        for r in parse_products(payload, shop, "https://x.test", TODAY):
            if r.set_number in watch and r.image:
                found.add(r.set_number)
    assert found == watch


def test_the_real_fixtures_yield_piece_counts_for_most_sets():
    found = {}
    for fixture, shop in [("official_products.json", "official"),
                          ("toycra_products.json", "toycra")]:
        payload = json.load(open(f"tests/fixtures/{fixture}"))
        for r in parse_products(payload, shop, "https://x.test", TODAY):
            if r.pieces:
                found[r.set_number] = r.pieces
    assert found.get("42172") == 3893
    assert found.get("11377") == 8278
    assert found.get("10316") == 6167


# --- what reaches the email ------------------------------------------

from legotracker.cli import build_report          # noqa: E402
from legotracker.config import load_config        # noqa: E402
from legotracker.models import PriceRow           # noqa: E402

T = load_config()["thresholds"]


def prow(shop="official", price=63999.0, image=None, pieces=None):
    return PriceRow(TODAY, shop, "10294", price, 63999.0, True,
                    "https://x.test/p", "feed", False, image, pieces)


def report(rows, entry=None):
    entry = entry or {"set": "10294", "name": "Titanic"}
    _, every = build_report(rows, [entry], [], TODAY, T)
    return every[0]


def test_the_report_carries_the_image():
    assert report([prow(image="https://cdn.test/a.png")])["image"] \
        == "https://cdn.test/a.png"


def test_an_image_from_any_shop_is_used():
    # The cheapest shop may not be the one with a picture.
    rows = [prow(shop="toycra", price=60000.0, image=None),
            prow(shop="official", price=63999.0, image="https://cdn.test/a.png")]
    assert report(rows)["image"] == "https://cdn.test/a.png"


def test_price_per_piece_is_computed():
    item = report([prow(price=63999.0, pieces=9090)])
    assert item["pieces"] == 9090
    assert round(item["price_per_piece"], 2) == 7.04


def test_price_per_piece_is_none_when_the_count_is_unknown():
    item = report([prow(price=63999.0, pieces=None)])
    assert item["price_per_piece"] is None


def test_a_watchlist_piece_count_fills_the_gap():
    item = report([prow(price=63999.0, pieces=None)],
                  entry={"set": "10294", "name": "Titanic", "pieces": 9090})
    assert round(item["price_per_piece"], 2) == 7.04


def test_a_watchlist_piece_count_overrides_a_scraped_one():
    # A hand-entered count is deliberate; a parsed one is a guess.
    item = report([prow(price=63999.0, pieces=1)],
                  entry={"set": "10294", "name": "Titanic", "pieces": 9090})
    assert item["pieces"] == 9090
