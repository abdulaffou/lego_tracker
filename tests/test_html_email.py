"""The HTML email: photo, price per piece, and the range bar."""
from legotracker.mailer import compose, compose_html
from legotracker.models import Verdict


def item(set_number="10294", name="Titanic", price=63999.0, shop="official",
         label="GOOD", position=17.0, pieces=9090, ppp=7.04,
         image="https://cdn.test/10294.png", low=57000.0, high=98999.0,
         mrp=63999.0):
    return {"set_number": set_number, "name": name, "price": price,
            "shop": shop, "url": f"https://x.test/{set_number}",
            "verdict": Verdict(label, position, "17% up its range", True),
            "sources": 1, "history_days": 3, "mrp": mrp, "in_stock": True,
            "image": image, "pieces": pieces, "price_per_piece": ppp,
            "range_low": low, "range_high": high}


def test_the_photo_is_shown():
    html = compose_html([item()], [], "2026-10-04")
    assert 'src="https://cdn.test/10294.png"' in html


def test_a_missing_photo_does_not_leave_a_broken_image():
    html = compose_html([item(image=None)], [], "2026-10-04")
    assert "<img" not in html


def test_price_per_piece_is_shown():
    html = compose_html([item()], [], "2026-10-04")
    assert "7.04" in html
    assert "9,090" in html


def test_price_per_piece_is_omitted_when_unknown():
    html = compose_html([item(pieces=None, ppp=None)], [], "2026-10-04")
    assert "per piece" not in html.lower()


def test_the_range_bar_marks_the_right_position():
    html = compose_html([item(position=17.0)], [], "2026-10-04")
    assert "left:17" in html.replace(" ", "")


def test_the_range_bar_shows_both_ends():
    html = compose_html([item()], [], "2026-10-04")
    assert "57,000" in html and "98,999" in html


def test_a_set_with_no_range_gets_no_bar():
    html = compose_html([item(position=None, low=None, high=None)], [],
                        "2026-10-04")
    assert "rangebar" not in html


def test_the_price_and_verdict_are_present():
    html = compose_html([item()], [], "2026-10-04")
    assert "63,999" in html
    assert "GOOD" in html.upper()


def test_styles_are_inline_because_gmail_strips_style_blocks():
    html = compose_html([item()], [], "2026-10-04")
    assert "<style" not in html.lower()
    assert 'style="' in html


def test_no_svg_because_gmail_will_not_render_it():
    html = compose_html([item()], [], "2026-10-04")
    assert "<svg" not in html.lower()


def test_non_ascii_names_survive():
    html = compose_html([item(name="RIVENDELL™")], [], "2026-10-04")
    assert "RIVENDELL™" in html


def test_a_name_with_markup_characters_is_escaped():
    html = compose_html([item(name="Tudor <b>Corner</b>")], [], "2026-10-04")
    assert "<b>Corner</b>" not in html
    assert "&lt;b&gt;" in html


def test_failed_shops_are_still_noted():
    html = compose_html([item()], ["toycra"], "2026-10-04")
    assert "toycra" in html.lower()


def test_the_plain_text_version_still_works():
    subject, body = compose([item()], [], "2026-10-04")
    assert "Titanic" in subject
    assert "63,999" in body


def test_the_plain_text_version_gained_price_per_piece():
    _, body = compose([item()], [], "2026-10-04")
    assert "7.04" in body


# --- the range ends have to reach the email --------------------------

from legotracker.config import load_config      # noqa: E402
from legotracker.verdict import judge            # noqa: E402

T = load_config()["thresholds"]


def test_judge_reports_the_anchors_it_used():
    v = judge(price=63999, mrp=63999, amazon_low=57000, amazon_high=98999,
              recorded_low=None, history_days=0, in_stock=True, stale=False,
              thresholds=T)
    assert v.low == 57000
    assert v.high == 98999


def test_anchors_are_none_on_the_mrp_fallback_path():
    v = judge(price=29399, mrp=41199, amazon_low=None, amazon_high=None,
              recorded_low=None, history_days=0, in_stock=True, stale=False,
              thresholds=T)
    assert v.low is None and v.high is None


# --- multipart send --------------------------------------------------

from legotracker.mailer import send               # noqa: E402


def test_send_carries_both_a_plain_and_an_html_version(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setattr("legotracker.mailer.smtplib.SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    send("subject", "plain body", {"email": {"to": "x", "from_addr": "x",
                                             "smtp_host": "h",
                                             "smtp_port": 587}},
         html="<div>rich body</div>")

    message = sent["msg"]
    types = {p.get_content_type() for p in message.walk()}
    assert "text/plain" in types
    assert "text/html" in types
    assert "rich body" in message.get_body(("html",)).get_content()


def test_send_without_html_stays_plain_text(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setattr("legotracker.mailer.smtplib.SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    send("s", "b", {"email": {"to": "x", "from_addr": "x",
                              "smtp_host": "h", "smtp_port": 587}})
    assert "text/html" not in {p.get_content_type()
                               for p in sent["msg"].walk()}
