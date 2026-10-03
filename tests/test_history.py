from legotracker.history import (append_rows, history_days, read_rows,
                                 recorded_low, sticky_mrp)
from legotracker.models import PriceRow


def row(date="2026-10-04", shop="official", set_number="10294", price=63999.0,
        mrp=None, in_stock=True, url="https://x.test/p", source="feed"):
    return PriceRow(date, shop, set_number, price, mrp, in_stock, url, source)


def test_append_then_read_round_trips(tmp_path):
    path = tmp_path / "prices.csv"
    append_rows(path, [row()])
    assert read_rows(path) == [row()]


def test_append_never_overwrites(tmp_path):
    path = tmp_path / "prices.csv"
    append_rows(path, [row(date="2026-10-04")])
    append_rows(path, [row(date="2026-10-05", price=60000.0)])
    assert len(read_rows(path)) == 2


def test_header_written_once(tmp_path):
    path = tmp_path / "prices.csv"
    append_rows(path, [row()])
    append_rows(path, [row(date="2026-10-05")])
    assert path.read_text(encoding="utf-8").count("set_number") == 1


def test_non_ascii_survives_round_trip(tmp_path):
    path = tmp_path / "prices.csv"
    url = "https://x.test/rivendell™"
    append_rows(path, [row(set_number="10316", url=url)])
    assert read_rows(path)[0].url == url


def test_in_stock_round_trips_as_bool_not_string(tmp_path):
    path = tmp_path / "prices.csv"
    append_rows(path, [row(in_stock=False)])
    assert read_rows(path)[0].in_stock is False


def test_mrp_none_round_trips_as_none(tmp_path):
    path = tmp_path / "prices.csv"
    append_rows(path, [row(mrp=None)])
    assert read_rows(path)[0].mrp is None


def test_reading_a_missing_file_gives_empty_list(tmp_path):
    assert read_rows(tmp_path / "nope.csv") == []


def test_sticky_mrp_takes_the_highest_ever_seen():
    rows = [row(date="2026-10-04", mrp=41199.0),
            row(date="2026-10-05", mrp=38000.0)]
    assert sticky_mrp(rows, "10294") == 41199.0


def test_sticky_mrp_falls_back_to_highest_price_when_no_list_price():
    rows = [row(date="2026-10-04", price=63999.0, mrp=None),
            row(date="2026-10-05", price=60000.0, mrp=None)]
    assert sticky_mrp(rows, "10294") == 63999.0


def test_sticky_mrp_unknown_set_is_none():
    assert sticky_mrp([row()], "99999") is None


def test_recorded_low_ignores_out_of_stock_prices():
    rows = [row(price=63999.0, in_stock=True),
            row(price=20000.0, in_stock=False)]
    assert recorded_low(rows, "10294") == 63999.0


def test_history_days_counts_distinct_dates():
    rows = [row(date="2026-10-04", shop="official"),
            row(date="2026-10-04", shop="toycra"),
            row(date="2026-10-05", shop="official")]
    assert history_days(rows, "10294") == 2


def test_appending_the_same_day_twice_replaces_rather_than_duplicates(tmp_path):
    path = tmp_path / "prices.csv"
    append_rows(path, [row(date="2026-10-04", price=63999.0)])
    append_rows(path, [row(date="2026-10-04", price=59999.0)])
    kept = read_rows(path)
    assert len(kept) == 1, "one row per (date, shop, set)"
    assert kept[0].price == 59999.0, "the later run wins"


def test_a_rerun_does_not_disturb_other_days(tmp_path):
    path = tmp_path / "prices.csv"
    append_rows(path, [row(date="2026-10-03", price=70000.0)])
    append_rows(path, [row(date="2026-10-04", price=63999.0)])
    append_rows(path, [row(date="2026-10-04", price=59999.0)])
    assert sorted(r.date for r in read_rows(path)) == ["2026-10-03",
                                                       "2026-10-04"]
