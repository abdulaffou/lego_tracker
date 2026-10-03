from legotracker.shops.amazon import parse_amazon_page, parse_price_history

TODAY = "2026-10-04"


def test_parses_the_real_mclaren_page():
    html = open("tests/fixtures/amazon_42172.html", encoding="utf-8",
                errors="ignore").read()
    row = parse_amazon_page(html, "42172", "https://amzn.test/dp/X", TODAY)
    assert row.price == 37079.0
    assert row.mrp == 41199.0
    assert row.shop == "amazon"
    assert row.source == "page"


def test_a_captcha_page_yields_none_not_a_crash():
    assert parse_amazon_page("<html>Enter the characters you see below</html>",
                             "42172", "https://amzn.test/dp/X", TODAY) is None


def test_empty_html_yields_none():
    assert parse_amazon_page("", "42172", "https://amzn.test/dp/X", TODAY) is None


def test_parses_the_real_titanic_price_history():
    html = open("tests/fixtures/pricehistory_10294.html", encoding="utf-8",
                errors="ignore").read()
    stats = parse_price_history(html)
    assert stats["low"] == 57000.0
    assert stats["high"] == 98999.0
    assert stats["average"] == 86415.0


def test_price_history_missing_fields_yields_none():
    assert parse_price_history("<html>nothing here</html>") is None


def test_price_history_rejects_a_low_above_the_high():
    html = "Lowest ... &#8377;90,000 ... Highest ... &#8377;10,000"
    assert parse_price_history(html) is None
