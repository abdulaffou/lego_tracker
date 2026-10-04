"""Review findings I5, I6, I7, I9: failures must never be silent."""
import requests

from legotracker.mailer import compose
from legotracker.models import Verdict
from legotracker.shops import fetch_all
from legotracker.shops import shopify


def item(set_number="10294", name="Titanic", label="GOOD"):
    return {"set_number": set_number, "name": name, "price": 63999.0,
            "shop": "official", "url": "https://x.test/p",
            "verdict": Verdict(label, 17.0, "17% up its range", True),
            "sources": 1, "history_days": 0}


# --- I9 / review focus 4: a shop failing mid-run ---------------------

def test_a_403_marks_the_shop_failed_and_does_not_raise(monkeypatch):
    def boom(*a, **k):
        raise requests.HTTPError("403 Forbidden")
    monkeypatch.setattr(shopify.requests, "get", boom)
    rows, ok = shopify.fetch_shop("toycra", "2026-10-04")
    assert rows == []
    assert ok is False


def test_a_timeout_does_not_raise(monkeypatch):
    def boom(*a, **k):
        raise requests.Timeout("timed out")
    monkeypatch.setattr(shopify.requests, "get", boom)
    assert shopify.fetch_shop("toycra", "2026-10-04") == ([], False)


def test_html_where_json_was_expected_does_not_raise(monkeypatch):
    class Resp:
        def raise_for_status(self): pass
        def json(self): raise ValueError("not json")
    monkeypatch.setattr(shopify.requests, "get", lambda *a, **k: Resp())
    assert shopify.fetch_shop("toycra", "2026-10-04") == ([], False)


def test_one_dead_shop_does_not_stop_the_others(monkeypatch):
    def selective(url, **kwargs):
        if "toycra" in url:
            raise requests.HTTPError("403")
        class Resp:
            def raise_for_status(self): pass
            def json(self):
                return {"products": [{
                    "title": "Titanic", "vendor": "LEGO", "handle": "t",
                    "variants": [{"sku": "10294", "price": "63999.00",
                                  "compare_at_price": None,
                                  "available": True}]}]}
        return Resp()
    monkeypatch.setattr(shopify.requests, "get", selective)
    rows, failed = fetch_all("2026-10-04")
    assert rows, "the healthy shops must still produce rows"
    assert "toycra" in failed


def test_a_failure_after_page_one_still_marks_the_shop_failed(monkeypatch):
    calls = {"n": 0}

    def flaky(url, params=None, **kwargs):
        calls["n"] += 1
        if calls["n"] > 1:
            raise requests.HTTPError("403 on page 2")
        class Resp:
            def raise_for_status(self): pass
            def json(self):
                return {"products": [{
                    "title": "Titanic", "vendor": "LEGO", "handle": "t",
                    "variants": [{"sku": "10294", "price": "63999.00",
                                  "compare_at_price": None,
                                  "available": True}]}]}
        return Resp()
    monkeypatch.setattr(shopify.requests, "get", flaky)
    rows, ok = shopify.fetch_shop("official", "2026-10-04")
    assert rows, "page 1 data is kept"
    assert ok is False, "a truncated catalogue is not a healthy fetch"


# --- I6: a dead shop is reported even when there is no other news ----

def test_a_failed_shop_is_reported_even_with_no_news():
    subject, body = compose([], ["toycra"], "2026-10-04")
    assert subject is not None, "silence would mean 'it broke weeks ago'"
    assert "toycra" in body.lower()


def test_a_totally_quiet_day_with_no_failures_sends_nothing():
    assert compose([], [], "2026-10-04") == (None, None)


# --- I7: the weekly digest ------------------------------------------

def test_the_digest_lists_everything_being_watched():
    subject, body = compose([], [], "2026-10-04",
                            digest=[item(), item("42172", "McLaren P1",
                                                 label="FAIR")])
    assert subject is not None
    assert "Titanic" in body and "McLaren P1" in body


def test_the_digest_names_sets_wanting_a_fresh_screenshot():
    stale_item = item()
    stale_item["stale"] = True
    _, body = compose([], [], "2026-10-04", digest=[stale_item])
    assert "screenshot" in body.lower()
