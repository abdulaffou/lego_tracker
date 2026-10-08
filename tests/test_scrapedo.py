"""Amazon through Scrape.do, on a free plan of 1,000 requests a month.

Amazon shows GitHub's servers a CAPTCHA, so the cloud run reads Amazon
through Scrape.do. Every request is counted, and the run stops spending
well before the plan runs out.
"""
from legotracker import usage as u
from legotracker.cli import fetch_amazon_rows
from legotracker.shops import amazon

TODAY = "2026-10-08"
MCLAREN = open("tests/fixtures/amazon_42172.html", encoding="utf-8",
               errors="ignore").read()


class Resp:
    def __init__(self, text, headers=None, status=200):
        self.text = text
        self.headers = headers or {}
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


# --- the Scrape.do call itself ---------------------------------------

def test_asks_scrapedo_for_the_amazon_in_page(monkeypatch):
    seen = {}

    def fake_get(url, params=None, timeout=None, **kw):
        seen.update(url=url, params=params)
        return Resp(MCLAREN, {"Scrape.do-Request-Cost": "1",
                              "Scrape.do-Remaining-Credits": "994"})

    monkeypatch.setattr(amazon.requests, "get", fake_get)
    row, spend = amazon.fetch_amazon_via_scrapedo(
        "B0CWH3TBGB", "42172", TODAY, "tok")

    assert seen["url"] == "https://api.scrape.do/plugin/amazon/"
    assert seen["params"] == {"token": "tok",
                              "url": "https://www.amazon.in/dp/B0CWH3TBGB",
                              "geocode": "in"}
    assert row.price == 37079.0
    assert row.url == "https://www.amazon.in/dp/B0CWH3TBGB"
    assert spend == {"credits": 1, "remaining": 994}


def test_a_failed_scrapedo_call_returns_none_and_costs_nothing(monkeypatch):
    def boom(*a, **k):
        raise TimeoutError("slow")

    monkeypatch.setattr(amazon.requests, "get", boom)
    row, spend = amazon.fetch_amazon_via_scrapedo("X", "42172", TODAY, "tok")
    assert row is None
    assert spend == {"credits": 0, "remaining": None}


def test_missing_cost_header_on_success_is_counted_as_one_credit(monkeypatch):
    monkeypatch.setattr(amazon.requests, "get",
                        lambda *a, **k: Resp(MCLAREN))
    _, spend = amazon.fetch_amazon_via_scrapedo("X", "42172", TODAY, "tok")
    assert spend == {"credits": 1, "remaining": None}


def test_the_token_never_appears_in_a_logged_error(monkeypatch, caplog):
    def boom(url, params=None, **k):
        raise RuntimeError(f"failed for {url}?token={params['token']}")

    monkeypatch.setattr(amazon.requests, "get", boom)
    amazon.fetch_amazon_via_scrapedo("X", "42172", TODAY, "secret-tok")
    assert "secret-tok" not in caplog.text


# --- the budget ------------------------------------------------------

def test_allowance_is_the_cap_less_what_this_month_used():
    usage = {"2026-10": {"requests": 100}}
    assert u.allowance(usage, TODAY, cap=900, remaining=None,
                       reserve=50) == 800


def test_allowance_respects_what_scrapedo_says_is_left():
    usage = {"2026-10": {"requests": 100}}
    assert u.allowance(usage, TODAY, cap=900, remaining=60,
                       reserve=50) == 10


def test_allowance_never_goes_negative():
    usage = {"2026-10": {"requests": 950}}
    assert u.allowance(usage, TODAY, cap=900, remaining=20,
                       reserve=50) == 0


def test_a_new_month_starts_a_fresh_count():
    usage = {"2026-09": {"requests": 900}}
    assert u.allowance(usage, TODAY, cap=900, remaining=None,
                       reserve=50) == 900


def test_record_counts_requests_credits_and_the_day():
    usage = {}
    u.record(usage, TODAY, {"credits": 1, "remaining": 999})
    u.record(usage, TODAY, {"credits": 0, "remaining": None})
    month = usage["2026-10"]
    assert month["requests"] == 2
    assert month["credits"] == 1
    assert month["remaining"] == 999      # a None never overwrites
    assert month["days"] == {TODAY: 2}


def test_summary_reads_plainly():
    usage = {"2026-10": {"requests": 42, "credits": 40, "remaining": 958,
                         "days": {TODAY: 6}}}
    assert u.summary(usage, TODAY, cap=900) == (
        "Scrape.do: 6 requests today, 42 of 900 this month, "
        "958 credits left")


def test_usage_round_trips_through_a_file(tmp_path):
    path = tmp_path / "usage.json"
    assert u.load_usage(path) == {}
    u.save_usage(path, {"2026-10": {"requests": 3}})
    assert u.load_usage(path) == {"2026-10": {"requests": 3}}


# --- the run: free first, paid only when free fails -------------------

WATCH = [{"set": "42172", "asin": "A1"}, {"set": "10350", "asin": "A2"},
         {"set": "11377"}]


def _row(set_number):
    return amazon.parse_amazon_page(MCLAREN, set_number, "u", TODAY)


def test_scrapedo_is_used_only_when_the_free_fetch_fails(monkeypatch):
    paid = []
    monkeypatch.setattr("legotracker.cli.fetch_amazon",
                        lambda asin, s, t: _row(s) if asin == "A1" else None)

    def via(asin, s, t, token):
        paid.append(asin)
        return _row(s), {"credits": 1, "remaining": 998}

    monkeypatch.setattr("legotracker.cli.fetch_amazon_via_scrapedo", via)
    usage = {}
    rows, failed = fetch_amazon_rows(WATCH, TODAY, token="tok", usage=usage,
                                     allowed=10, local=False)
    assert paid == ["A2"]
    assert sorted(r.set_number for r in rows) == ["10350", "42172"]
    assert failed == []
    assert usage["2026-10"]["requests"] == 1


def test_no_token_means_no_paid_calls(monkeypatch):
    monkeypatch.setattr("legotracker.cli.fetch_amazon",
                        lambda *a: None)
    monkeypatch.setattr("legotracker.cli.fetch_amazon_via_scrapedo",
                        lambda *a: (_ for _ in ()).throw(AssertionError))
    rows, failed = fetch_amazon_rows(WATCH, TODAY, token=None, usage={},
                                     allowed=10, local=False)
    assert rows == []
    assert failed == []          # the cloud run without a token: as before


def test_spending_stops_at_the_allowance_and_says_so(monkeypatch):
    paid = []
    monkeypatch.setattr("legotracker.cli.fetch_amazon", lambda *a: None)

    def via(asin, s, t, token):
        paid.append(asin)
        return _row(s), {"credits": 1, "remaining": 51}

    monkeypatch.setattr("legotracker.cli.fetch_amazon_via_scrapedo", via)
    rows, failed = fetch_amazon_rows(WATCH, TODAY, token="tok", usage={},
                                     allowed=1, local=False)
    assert paid == ["A1"]
    assert "amazon:10350" in failed
    assert "scrape.do budget used up" in failed


def test_a_paid_call_that_fails_is_reported(monkeypatch):
    monkeypatch.setattr("legotracker.cli.fetch_amazon", lambda *a: None)
    monkeypatch.setattr("legotracker.cli.fetch_amazon_via_scrapedo",
                        lambda *a: (None, {"credits": 0, "remaining": None}))
    _, failed = fetch_amazon_rows(WATCH, TODAY, token="tok", usage={},
                                  allowed=10, local=False)
    assert failed == ["amazon:42172", "amazon:10350"]


# --- hardening: a paid request must never be wasted silently ---------

def test_odd_cost_headers_do_not_crash_after_the_credit_is_spent(monkeypatch):
    monkeypatch.setattr(amazon.requests, "get", lambda *a, **k: Resp(
        MCLAREN, {"Scrape.do-Request-Cost": "1.0",
                  "Scrape.do-Remaining-Credits": "n/a"}))
    row, spend = amazon.fetch_amazon_via_scrapedo("X", "42172", TODAY, "tok")
    assert row.price == 37079.0
    assert spend == {"credits": 1, "remaining": None}


def test_a_paid_page_that_does_not_parse_says_what_came_back(monkeypatch,
                                                             caplog):
    page = "<html><title>Deliver to your location</title><p>hi</p></html>"
    monkeypatch.setattr(amazon.requests, "get",
                        lambda *a, **k: Resp(page))
    row, _ = amazon.fetch_amazon_via_scrapedo("X", "42172", TODAY,
                                              "secret-tok")
    assert row is None
    assert "Deliver to your location" in caplog.text
    assert "priceToPay" in caplog.text
    assert "secret-tok" not in caplog.text


def test_the_balance_from_scrapedo_is_kept_for_the_email():
    usage = {}
    u.note_balance(usage, TODAY, 994)
    assert u.summary(usage, TODAY, cap=900).endswith("994 credits left")
    u.note_balance(usage, TODAY, None)          # a failed check keeps it
    assert usage["2026-10"]["remaining"] == 994
