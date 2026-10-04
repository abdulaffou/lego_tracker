import json

from legotracker.models import PriceRow
from legotracker.shops.shopify import parse_products

TODAY = "2026-10-04"


def load(name):
    return json.load(open(f"tests/fixtures/{name}"))


def rows_for(shop, fixture, base="https://example.test"):
    return parse_products(load(fixture), shop, base, TODAY)


def test_official_store_parses_watchlist_sets():
    rows = rows_for("official", "official_products.json")
    by_set = {r.set_number: r for r in rows}
    assert by_set["10294"].price == 63999.0      # Titanic
    assert by_set["42172"].price == 41199.0      # McLaren at MRP
    assert by_set["11389"].price == 11999.0      # Project Hail Mary


def test_toycra_parses_the_mclaren_deal():
    rows = rows_for("toycra", "toycra_products.json")
    by_set = {r.set_number: r for r in rows}
    assert by_set["42172"].price == 29399.0
    assert by_set["42172"].mrp == 41199.0


def test_funcorp_balloons_never_become_rows():
    rows = rows_for("funcorp", "funcorp_products.json")
    for trap in ("10350", "10316", "10294"):
        matches = [r for r in rows if r.set_number == trap and r.price < 1000]
        assert matches == [], f"a sub-1000-rupee product matched set {trap}"


def test_rows_carry_the_shop_and_date():
    rows = rows_for("official", "official_products.json")
    assert all(r.shop == "official" for r in rows)
    assert all(r.date == TODAY for r in rows)
    assert all(r.source == "feed" for r in rows)


def test_absent_compare_at_price_gives_mrp_none_not_zero():
    payload = {"products": [{
        "title": "Tudor Corner", "vendor": "LEGO", "handle": "tudor-corner",
        "variants": [{"sku": "10350", "price": "24499.00",
                      "compare_at_price": None, "available": True}]}]}
    row = parse_products(payload, "official", "https://x.test", TODAY)[0]
    assert row.mrp is None


def test_compare_at_price_equal_to_price_is_kept():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "titanic",
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": "63999.00", "available": True}]}]}
    row = parse_products(payload, "official", "https://x.test", TODAY)[0]
    assert row.mrp == 63999.0


def test_out_of_stock_is_recorded_not_dropped():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "titanic",
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": None, "available": False}]}]}
    row = parse_products(payload, "official", "https://x.test", TODAY)[0]
    assert row.in_stock is False


def test_toycra_missing_available_field_defaults_to_in_stock():
    # Toycra's collection feed only ever lists in-stock items.
    payload = {"products": [{
        "title": "Lego 42172", "vendor": "LEGO", "handle": "mclaren",
        "variants": [{"sku": "Lego42172", "price": "29399.00",
                      "compare_at_price": "41199.00"}]}]}
    row = parse_products(payload, "toycra", "https://x.test", TODAY)[0]
    assert row.in_stock is True


def test_cheapest_variant_wins_when_a_set_appears_twice():
    payload = {"products": [
        {"title": "Titanic", "vendor": "LEGO", "handle": "titanic-a",
         "variants": [{"sku": "10294", "price": "70000.00",
                       "compare_at_price": None, "available": True}]},
        {"title": "Titanic", "vendor": "LEGO", "handle": "titanic-b",
         "variants": [{"sku": "10294", "price": "63999.00",
                       "compare_at_price": None, "available": True}]}]}
    rows = parse_products(payload, "official", "https://x.test", TODAY)
    assert len(rows) == 1
    assert rows[0].price == 63999.0


def test_url_points_at_the_product():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "titanic-10294",
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": None, "available": True}]}]}
    row = parse_products(payload, "official", "https://shop.test", TODAY)[0]
    assert row.url == "https://shop.test/products/titanic-10294"


def test_garbage_payload_yields_no_rows_and_does_not_raise():
    assert parse_products({}, "official", "https://x.test", TODAY) == []
    assert parse_products({"products": None}, "official", "https://x.test", TODAY) == []


def test_unparseable_price_is_skipped_not_crashed():
    payload = {"products": [{
        "title": "Broken", "vendor": "LEGO", "handle": "broken",
        "variants": [{"sku": "10294", "price": "ask us",
                      "compare_at_price": None, "available": True}]}]}
    assert parse_products(payload, "official", "https://x.test", TODAY) == []


def test_non_ascii_titles_survive():
    payload = {"products": [{
        "title": "THE LORD OF THE RINGS: RIVENDELL™", "vendor": "LEGO",
        "handle": "rivendell",
        "variants": [{"sku": "10316", "price": "50399.00",
                      "compare_at_price": None, "available": True}]}]}
    row = parse_products(payload, "official", "https://x.test", TODAY)[0]
    assert row.set_number == "10316"
