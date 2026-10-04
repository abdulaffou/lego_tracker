from legotracker.mailer import compose
from legotracker.models import Verdict


def item(set_number="10294", name="Titanic", price=63999.0, shop="official",
         label="GOOD", reason="17% up its range (Rs57,000-Rs98,999)",
         sources=1, history_days=0):
    return {"set_number": set_number, "name": name, "price": price,
            "shop": shop, "url": f"https://x.test/{set_number}",
            "verdict": Verdict(label, 17.0, reason, True),
            "sources": sources, "history_days": history_days}


def test_subject_names_the_best_deal():
    subject, _ = compose([item()], [], "2026-10-04")
    assert "Titanic" in subject


def test_body_shows_price_shop_and_reason():
    _, body = compose([item()], [], "2026-10-04")
    assert "63,999" in body
    assert "official" in body
    assert "17% up its range" in body


def test_body_links_to_the_product():
    _, body = compose([item()], [], "2026-10-04")
    assert "https://x.test/10294" in body


def test_body_states_how_much_evidence_there_is():
    _, body = compose([item(sources=1, history_days=0)], [], "2026-10-04")
    assert "1 shop" in body
    assert "0 days" in body


def test_buy_now_sorts_above_good():
    items = [item("10294", "Titanic", label="GOOD"),
             item("42172", "McLaren P1", label="BUY_NOW")]
    _, body = compose(items, [], "2026-10-04")
    assert body.index("McLaren P1") < body.index("Titanic")


def test_failed_shops_are_named_in_a_footer():
    _, body = compose([item()], ["amazon"], "2026-10-04")
    assert "amazon" in body.lower()


def test_non_ascii_names_do_not_raise():
    _, body = compose([item(name="RIVENDELL™")], [], "2026-10-04")
    assert "RIVENDELL™" in body
    body.encode("utf-8")  # must not raise


def test_no_items_and_no_failures_composes_nothing():
    assert compose([], [], "2026-10-04") == (None, None)


def test_all_shops_failed_sends_a_warning_even_with_no_items():
    subject, body = compose([], ["official", "toycra", "funcorp"],
                            "2026-10-04")
    assert subject is not None
    assert "could not check" in body.lower()
