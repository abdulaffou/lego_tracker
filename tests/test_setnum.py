import json

from legotracker.setnum import extract_set_number, is_lego

FIXTURES = "tests/fixtures"


def test_extracts_bare_number():
    assert extract_set_number("43269") == "43269"


def test_extracts_from_toycra_prefix():
    assert extract_set_number("Lego42172") == "42172"


def test_extracts_from_funcorp_prefix():
    assert extract_set_number("LEG-77243") == "77243"


def test_returns_none_for_empty_sku():
    assert extract_set_number("") is None
    assert extract_set_number(None) is None


def test_returns_none_when_no_digits():
    assert extract_set_number("GIFTCARD") is None


def test_balloon_sku_still_yields_a_number():
    # Documents WHY is_lego is required: extraction alone cannot save us.
    assert extract_set_number("PCP-LBL10350") == "10350"


def test_funcorp_balloons_are_rejected_as_not_lego():
    products = json.load(open(f"{FIXTURES}/funcorp_products.json"))["products"]
    traps = [p for p in products
             if (p["variants"][0].get("sku") or "").startswith("PCP-")]
    assert traps, "fixture must contain the PartyCorp traps"
    for p in traps:
        assert is_lego(p, "funcorp") is False


def test_funcorp_real_lego_is_accepted():
    products = json.load(open(f"{FIXTURES}/funcorp_products.json"))["products"]
    legos = [p for p in products if (p.get("vendor") or "").lower() == "lego"]
    assert legos, "fixture must contain real LEGO"
    for p in legos:
        assert is_lego(p, "funcorp") is True


def test_official_store_accepts_everything():
    # Titles like "Project Hail Mary" never say LEGO, but the shop is LEGO-only.
    assert is_lego({"title": "Project Hail Mary", "vendor": "LEGO"}, "official")
    assert is_lego({"title": "Tudor Corner", "vendor": "Ample Technologies Pvt Ltd"},
                   "official")


def test_toycra_accepts_everything():
    assert is_lego({"title": "Lego 42172 Technic McLaren P1", "vendor": "LEGO"},
                   "toycra")


def test_unknown_shop_is_rejected_rather_than_trusted():
    assert is_lego({"title": "x", "vendor": "LEGO"}, "some-new-shop") is False
