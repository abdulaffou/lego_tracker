from legotracker.alerts import (is_absurd, is_news, load_state, record_alert,
                                save_state)
from legotracker.models import Verdict

GOOD = Verdict("GOOD", 17.0, "17% up its range", True)
BUY = Verdict("BUY_NOW", 5.0, "5% up its range", True)
WAIT = Verdict("WAIT", 80.0, "80% up its range", False)


def test_missing_state_file_loads_empty(tmp_path):
    assert load_state(tmp_path / "nope.json") == {}


def test_state_round_trips(tmp_path):
    path = tmp_path / "state.json"
    save_state(path, {"10294": {"label": "GOOD", "price": 63999.0,
                                "date": "2026-10-04"}})
    assert load_state(path)["10294"]["price"] == 63999.0


def test_first_ever_alertable_verdict_is_news():
    assert is_news("10294", GOOD, 63999.0, {}, "2026-10-04", 7) is True


def test_non_alertable_verdict_is_never_news():
    assert is_news("10294", WAIT, 63999.0, {}, "2026-10-04", 7) is False


def test_same_verdict_same_price_next_day_is_not_news():
    state = {}
    record_alert(state, "10294", GOOD, 63999.0, "2026-10-04")
    assert is_news("10294", GOOD, 63999.0, state, "2026-10-05", 7) is False


def test_a_lower_price_is_news_even_inside_the_cooldown():
    state = {}
    record_alert(state, "10294", GOOD, 63999.0, "2026-10-04")
    assert is_news("10294", GOOD, 60000.0, state, "2026-10-05", 7) is True


def test_an_upgraded_verdict_is_news_even_inside_the_cooldown():
    state = {}
    record_alert(state, "10294", GOOD, 63999.0, "2026-10-04")
    assert is_news("10294", BUY, 63999.0, state, "2026-10-05", 7) is True


def test_same_price_after_the_cooldown_is_news_again():
    state = {}
    record_alert(state, "10294", GOOD, 63999.0, "2026-10-04")
    assert is_news("10294", GOOD, 63999.0, state, "2026-10-12", 7) is True


def test_a_higher_price_inside_the_cooldown_is_not_news():
    state = {}
    record_alert(state, "10294", GOOD, 63999.0, "2026-10-04")
    assert is_news("10294", GOOD, 64500.0, state, "2026-10-05", 7) is False


def test_absurd_swing_detection():
    assert is_absurd(5000.0, 60000.0, 70) is True     # a 92% crash
    assert is_absurd(50000.0, 60000.0, 70) is False   # a plausible 17% drop
    assert is_absurd(50000.0, None, 70) is False      # nothing to compare to
