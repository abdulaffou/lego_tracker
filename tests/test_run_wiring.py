"""Review findings I7, I8, I9/I10: digest day, file growth, SMTP encoding."""
from legotracker.cli import is_digest_day
from legotracker.history import append_rows, read_all, year_path
from legotracker.mailer import send
from legotracker.models import PriceRow


def row(date="2026-10-04", price=63999.0):
    return PriceRow(date, "official", "10294", price, None, True,
                    "https://x.test/p", "feed")


def test_sunday_is_digest_day():
    assert is_digest_day("2026-10-04") is True     # a Sunday
    assert is_digest_day("2026-10-05") is False    # Monday


# --- I8: the history file must not grow without bound ---------------

def test_prices_are_written_to_a_file_per_year(tmp_path):
    base = tmp_path / "prices.csv"
    assert year_path(base, "2026-10-04").name == "prices-2026.csv"
    assert year_path(base, "2027-01-01").name == "prices-2027.csv"


def test_reading_history_spans_every_year_file(tmp_path):
    base = tmp_path / "prices.csv"
    append_rows(year_path(base, "2026-10-04"), [row("2026-10-04")])
    append_rows(year_path(base, "2027-01-02"), [row("2027-01-02", 50000.0)])
    dates = sorted(r.date for r in read_all(base))
    assert dates == ["2026-10-04", "2027-01-02"]


def test_reading_history_still_picks_up_a_legacy_unsuffixed_file(tmp_path):
    base = tmp_path / "prices.csv"
    append_rows(base, [row("2026-09-01")])
    append_rows(year_path(base, "2026-10-04"), [row("2026-10-04")])
    assert len(read_all(base)) == 2


# --- I9 / I10: the SMTP leg, with non-ASCII --------------------------

def test_send_encodes_a_trademark_sign_in_subject_and_body(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setattr("legotracker.mailer.smtplib.SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "me@example.test")
    monkeypatch.setenv("SMTP_PASS", "app-password")

    config = {"email": {"to": "me@example.test",
                        "from_addr": "me@example.test",
                        "smtp_host": "smtp.test", "smtp_port": 587}}
    send("LEGO: GOOD on RIVENDELL™", "RIVENDELL™ -- Rs40,399",
         config)

    message = sent["msg"]
    assert "RIVENDELL™" in str(message["Subject"])
    assert "RIVENDELL™" in message.get_content()
    bytes(message)  # must not raise


def test_send_reports_a_missing_secret_clearly(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    config = {"email": {"to": "x", "from_addr": "x",
                        "smtp_host": "h", "smtp_port": 587}}
    try:
        send("s", "b", config)
    except RuntimeError as exc:
        assert "SMTP_USER" in str(exc)
    else:
        raise AssertionError("a missing secret must raise RuntimeError")


# --- the spreadsheet attachment -------------------------------------

def test_send_attaches_the_workbook(monkeypatch, tmp_path):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setattr("legotracker.mailer.smtplib.SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "me@example.test")
    monkeypatch.setenv("SMTP_PASS", "pw")

    book = tmp_path / "lego-prices.xlsx"
    book.write_bytes(b"PK\x03\x04 fake xlsx")
    config = {"email": {"to": "me@example.test",
                        "from_addr": "me@example.test",
                        "smtp_host": "h", "smtp_port": 587}}
    send("subject", "body", config, attachment=book)

    names = [p.get_filename() for p in sent["msg"].iter_attachments()]
    assert "lego-prices.xlsx" in names


def test_send_works_with_no_attachment(monkeypatch):
    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): pass

    monkeypatch.setattr("legotracker.mailer.smtplib.SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASS", "p")
    send("s", "b", {"email": {"to": "x", "from_addr": "x",
                              "smtp_host": "h", "smtp_port": 587}})


def test_a_missing_attachment_file_does_not_stop_the_email(monkeypatch,
                                                           tmp_path):
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
                              "smtp_host": "h", "smtp_port": 587}},
         attachment=tmp_path / "nope.xlsx")
    assert sent["msg"] is not None, "the news matters more than the sheet"
