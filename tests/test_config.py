from legotracker.config import load_config, load_watchlist


def test_config_has_all_thresholds():
    cfg = load_config()
    t = cfg["thresholds"]
    assert t["buy_now_pct"] == 10
    assert t["good_pct"] == 25
    assert t["narrow_range_pct"] == 10
    assert t["min_history_days"] == 14
    assert t["stale_days"] == 180


def test_watchlist_loads_all_eight_sets():
    w = load_watchlist()
    assert len(w) == 8
    numbers = {s["set"] for s in w}
    assert numbers == {"11389", "10294", "11377", "10350",
                       "11371", "76269", "42172", "10316"}


def test_set_numbers_are_strings_not_ints():
    # "10294" must never become 10294 -- leading zeros exist in LEGO numbers
    for s in load_watchlist():
        assert isinstance(s["set"], str)


def test_minas_tirith_has_no_amazon_figures():
    w = {s["set"]: s for s in load_watchlist()}
    assert "amazon_low" not in w["11377"]
