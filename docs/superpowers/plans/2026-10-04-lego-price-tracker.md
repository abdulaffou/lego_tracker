# LEGO Price Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily job that checks LEGO prices across four Indian shops and emails Abdul only when a watchlist set reaches a genuinely good price.

**Architecture:** Five isolated stages — fetch, match, record, judge, alert — wired by a CLI. Shops are independent modules behind one interface, so a failing shop is a missing row, not a crashed run. Price history is an append-only CSV committed to the repo. The verdict is one rule: where today's price sits between the cheapest and dearest a set is known to have been.

**Tech Stack:** Python 3.11+, `requests` + `certifi` (the Mac's system SSL certs are broken), `PyYAML`, `pytest`. No database, no browser, no paid API.

**Spec:** `docs/superpowers/specs/2026-10-04-lego-price-tracker-design.md`

## Global Constraints

- Python 3.11+, all work inside a `.venv`. **Never use `urllib` directly** — the Mac fails with `CERTIFICATE_VERIFY_FAILED`; always `requests`, which uses `certifi`.
- Every HTTP call: `timeout=30`, a desktop browser `User-Agent`, and wrapped so a failure returns empty rather than raising.
- Shopify data comes from the **collection** endpoint (`/collections/<x>/products.json`), never the single-product one — the latter omits `available`.
- Money is `float` rupees throughout. Dates are ISO `YYYY-MM-DD` strings.
- `data/prices.csv` is **append-only**. No step may rewrite or delete existing rows.
- Thresholds live in `config.yaml`, never hardcoded in logic: buy ≤10%, good ≤25%, fair <50%, narrow-range <10%, MRP fallback ≥15%, stale 180 days, min-history 14 days, cooldown 7 days, absurd swing 70%.
- Secrets (`SMTP_USER`, `SMTP_PASS`) come from environment variables only. Never commit them, never log them.
- Fixtures in `tests/fixtures/` are real captured shop data. Tests must not hit the network.

## Review Focus

1. **A non-LEGO product whose SKU contains a watchlist set number.** `PCP-LBL10350` (a ₹59 PartyCorp balloon) yields `10350` — Tudor Corner, ₹24,499. Must be rejected by the vendor rule, never recorded. Already present in real data. *(Task 2)*
2. **Range anchors equal or inverted.** `high == low` must not divide by zero, and a price *above* the high anchor must give WAIT, not a negative position that reads as a bargain. *(Task 5)*
3. **A shop publishing no list price.** `compare_at_price` is routinely `null` or equal to `price`; MRP must fall back to the sticky maximum, never to `None` propagating into arithmetic. *(Tasks 3, 4)*
4. **One shop failing mid-run.** HTTP 403, a timeout, or HTML where JSON was expected must drop that shop only; the other three still record and the email still sends with a footer note. *(Tasks 3, 9)*
5. **Non-ASCII set names.** Real titles contain `™` and `—` (`THE LORD OF THE RINGS: RIVENDELL™`). These must survive the CSV round-trip and the email body without mangling or raising `UnicodeEncodeError`. *(Tasks 4, 8)*

---

## File Structure

```
Makefile                        setup / test / check / run
requirements.txt
config.yaml                     thresholds + email settings
watchlist.yaml                  the 8 sets (already drafted in spec §15)
data/prices.csv                 append-only history
data/alert_state.json           what we last told the user
src/legotracker/
    __init__.py
    config.py                   load config.yaml + watchlist.yaml
    models.py                   PriceRow, Anchors, Verdict
    setnum.py                   SKU -> set number, and "is this LEGO?"
    shops/__init__.py           SHOPS registry + fetch_all()
    shops/shopify.py            the three Shopify feeds
    shops/amazon.py             ASIN page + pricehistory.app
    history.py                  CSV read/append, sticky MRP, recorded low
    verdict.py                  the one rule
    alerts.py                   news detection, cooldown, state
    mailer.py                   compose + send
    cli.py                      entry point
tests/
    fixtures/                   real captured data (already saved)
    test_setnum.py  test_shopify.py  test_history.py  test_verdict.py
    test_amazon.py  test_alerts.py   test_mailer.py   test_end_to_end.py
.github/workflows/daily.yml
README.md
```

---

### Task 1: Project skeleton and config

**Files:**
- Create: `requirements.txt`, `Makefile`, `config.yaml`, `watchlist.yaml`, `.gitignore` (append)
- Create: `src/legotracker/__init__.py`, `src/legotracker/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `load_config(path="config.yaml") -> dict`, `load_watchlist(path="watchlist.yaml") -> list[dict]`

- [ ] **Step 1: Create the dependency and build files**

`requirements.txt`:
```
requests==2.32.3
certifi==2024.8.30
PyYAML==6.0.2
pytest==8.3.3
```

`Makefile` (tabs, not spaces, for the recipe lines):
```makefile
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

setup:
	python3 -m venv $(VENV)
	$(PIP) install -q -r requirements.txt

test:
	$(VENV)/bin/pytest -q

check:
	$(PY) -m legotracker.cli --local

run:
	$(PY) -m legotracker.cli
```

Append to `.gitignore`:
```
.venv/
```

- [ ] **Step 2: Create config.yaml**

```yaml
thresholds:
  buy_now_pct: 10
  good_pct: 25
  fair_pct: 50
  narrow_range_pct: 10
  mrp_fallback_discount_pct: 15
  stale_days: 180
  min_history_days: 14
  cooldown_days: 7
  absurd_swing_pct: 70

email:
  to: abdul.affou@enru.io
  from_addr: abdul.affou@enru.io
  smtp_host: smtp.gmail.com
  smtp_port: 587

paths:
  prices: data/prices.csv
  state: data/alert_state.json
```

- [ ] **Step 3: Create watchlist.yaml**

Copy verbatim from spec §15:

```yaml
- set: "11389"
  name: Project Hail Mary
  amazon_low: 11999
  amazon_high: 11999
  seen_on: 2026-10-04

- set: "10294"
  name: Titanic
  asin: B09GPPP2NK
  amazon_low: 57000
  amazon_high: 98999
  seen_on: 2026-10-04

- set: "11377"
  name: Minas Tirith

- set: "10350"
  name: Tudor Corner
  amazon_low: 14500
  amazon_high: 24501
  seen_on: 2026-10-04

- set: "11371"
  name: Shopping Street
  amazon_low: 24479
  amazon_high: 25999
  seen_on: 2026-10-04

- set: "76269"
  name: Avengers Tower
  amazon_low: 24501
  amazon_high: 48021
  seen_on: 2026-10-04

- set: "42172"
  name: McLaren P1
  asin: B0CWH3TBGB
  amazon_low: 20600
  amazon_high: 40490
  seen_on: 2026-10-04

- set: "10316"
  name: Rivendell
  amazon_low: 25200
  amazon_high: 45392
  seen_on: 2026-10-04
```

- [ ] **Step 4: Write the failing test**

`tests/test_config.py`:
```python
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
    # "10294" must never become 10294 — leading zeros exist in LEGO numbers
    for s in load_watchlist():
        assert isinstance(s["set"], str)


def test_minas_tirith_has_no_amazon_figures():
    w = {s["set"]: s for s in load_watchlist()}
    assert "amazon_low" not in w["11377"]
```

- [ ] **Step 5: Run test to verify it fails**

```bash
make setup && make test
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker'`

- [ ] **Step 6: Write the implementation**

`src/legotracker/__init__.py`: empty file.

`src/legotracker/config.py`:
```python
"""Loading of config.yaml and watchlist.yaml."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: str = "config.yaml") -> dict:
    with open(ROOT / path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_watchlist(path: str = "watchlist.yaml") -> list[dict]:
    with open(ROOT / path, encoding="utf-8") as fh:
        entries = yaml.safe_load(fh)
    for entry in entries:
        entry["set"] = str(entry["set"])
    return entries
```

Create `pytest.ini` so `src/` is importable:
```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
make test
```
Expected: 4 passed

- [ ] **Step 8: Commit**

```bash
git add requirements.txt Makefile config.yaml watchlist.yaml pytest.ini .gitignore src tests
git commit -m "feat: project skeleton, config and watchlist loading"
```

---

### Task 2: Set number extraction and LEGO identity

This is the task that prevents a ₹59 balloon being recorded as a ₹24,499 LEGO set. Read Review Focus item 1 before starting.

**Files:**
- Create: `src/legotracker/setnum.py`
- Test: `tests/test_setnum.py`

**Interfaces:**
- Consumes: nothing
- Produces: `extract_set_number(sku: str) -> str | None`, `is_lego(product: dict, shop: str) -> bool`

- [ ] **Step 1: Write the failing test**

`tests/test_setnum.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_setnum.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker.setnum'`

- [ ] **Step 3: Write the implementation**

`src/legotracker/setnum.py`:
```python
"""Turning shop SKUs into LEGO set numbers, safely.

Two rules, both required (see spec section 5):

  1. Read the set number from the SKU, never the product title.
  2. The shop must agree the product is LEGO.

Rule 2 is not a nicety. FunCorp sells party goods with SKUs like
PCP-LBL10350, which contains "10350" -- the number of a 24,499 rupee
LEGO set. Without the vendor check, a 59 rupee balloon is recorded as
that set crashing in price.
"""
import re

SET_NUMBER = re.compile(r"(\d{4,7})")

# Per-shop rule for "is this product actually LEGO?"
#   True        -> the whole catalogue is LEGO, accept everything
#   a string    -> require vendor to equal it, case-insensitively
SHOP_LEGO_RULE: dict[str, object] = {
    "official": True,    # LEGO-only shop
    "toycra": True,      # we only read /collections/lego
    "funcorp": "lego",   # general toy shop, 2000 products, 129 LEGO
}


def extract_set_number(sku: str | None) -> str | None:
    """First run of 4-7 digits in the SKU, or None.

    Returns a digit STRING, never an int: leading zeros are significant.
    """
    if not sku:
        return None
    match = SET_NUMBER.search(sku)
    return match.group(1) if match else None


def is_lego(product: dict, shop: str) -> bool:
    """Whether this shop vouches for the product being LEGO."""
    rule = SHOP_LEGO_RULE.get(shop)
    if rule is True:
        return True
    if isinstance(rule, str):
        return (product.get("vendor") or "").lower() == rule
    return False  # unknown shop: refuse rather than guess
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_setnum.py -q
```
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/legotracker/setnum.py tests/test_setnum.py
git commit -m "feat: set number extraction with vendor guard against SKU collisions"
```

---

### Task 3: Shopify shop reader

**Files:**
- Create: `src/legotracker/models.py`, `src/legotracker/shops/__init__.py`, `src/legotracker/shops/shopify.py`
- Test: `tests/test_shopify.py`

**Interfaces:**
- Consumes: `extract_set_number`, `is_lego` from Task 2
- Produces:
  - `PriceRow` dataclass with fields `date, shop, set_number, price, mrp, in_stock, url, source`
  - `parse_products(payload: dict, shop: str, base_url: str, today: str) -> list[PriceRow]`
  - `fetch_shop(shop: str, today: str) -> list[PriceRow]` (network; returns `[]` on any failure)
  - `SHOPIFY_SHOPS: dict[str, dict]`

- [ ] **Step 1: Write the failing test**

`tests/test_shopify.py`:
```python
import json

from legotracker.models import PriceRow
from legotracker.shops.shopify import parse_products

TODAY = "2026-10-04"


def load(name):
    return json.load(open(f"tests/fixtures/{name}"))


def rows_for(shop, fixture, base="https://example.test"):
    return parse_products(load(fixture), shop, base, TODAY)


def test_official_store_parses_watchlist_sets():
    rows = rows_for("official", "official_products.json")
    by_set = {r.set_number: r for r in rows}
    assert by_set["10294"].price == 63999.0      # Titanic
    assert by_set["42172"].price == 41199.0      # McLaren at MRP
    assert by_set["11389"].price == 11999.0      # Project Hail Mary


def test_toycra_parses_the_mclaren_deal():
    rows = rows_for("toycra", "toycra_products.json")
    by_set = {r.set_number: r for r in rows}
    assert by_set["42172"].price == 29399.0
    assert by_set["42172"].mrp == 41199.0


def test_funcorp_balloons_never_become_rows():
    rows = rows_for("funcorp", "funcorp_products.json")
    for trap in ("10350", "10316", "10294"):
        matches = [r for r in rows if r.set_number == trap and r.price < 1000]
        assert matches == [], f"a sub-1000-rupee product matched set {trap}"


def test_rows_carry_the_shop_and_date():
    rows = rows_for("official", "official_products.json")
    assert all(r.shop == "official" for r in rows)
    assert all(r.date == TODAY for r in rows)
    assert all(r.source == "feed" for r in rows)


def test_absent_compare_at_price_gives_mrp_none_not_zero():
    payload = {"products": [{
        "title": "Tudor Corner", "vendor": "LEGO", "handle": "tudor-corner",
        "variants": [{"sku": "10350", "price": "24499.00",
                      "compare_at_price": None, "available": True}]}]}
    row = parse_products(payload, "official", "https://x.test", TODAY)[0]
    assert row.mrp is None


def test_compare_at_price_equal_to_price_is_kept():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "titanic",
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": "63999.00", "available": True}]}]}
    row = parse_products(payload, "official", "https://x.test", TODAY)[0]
    assert row.mrp == 63999.0


def test_out_of_stock_is_recorded_not_dropped():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "titanic",
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": None, "available": False}]}]}
    row = parse_products(payload, "official", "https://x.test", TODAY)[0]
    assert row.in_stock is False


def test_toycra_missing_available_field_defaults_to_in_stock():
    # Toycra's collection feed only ever lists in-stock items.
    payload = {"products": [{
        "title": "Lego 42172", "vendor": "LEGO", "handle": "mclaren",
        "variants": [{"sku": "Lego42172", "price": "29399.00",
                      "compare_at_price": "41199.00"}]}]}
    row = parse_products(payload, "toycra", "https://x.test", TODAY)[0]
    assert row.in_stock is True


def test_cheapest_variant_wins_when_a_set_appears_twice():
    payload = {"products": [
        {"title": "Titanic", "vendor": "LEGO", "handle": "titanic-a",
         "variants": [{"sku": "10294", "price": "70000.00",
                       "compare_at_price": None, "available": True}]},
        {"title": "Titanic", "vendor": "LEGO", "handle": "titanic-b",
         "variants": [{"sku": "10294", "price": "63999.00",
                       "compare_at_price": None, "available": True}]}]}
    rows = parse_products(payload, "official", "https://x.test", TODAY)
    assert len(rows) == 1
    assert rows[0].price == 63999.0


def test_url_points_at_the_product():
    payload = {"products": [{
        "title": "Titanic", "vendor": "LEGO", "handle": "titanic-10294",
        "variants": [{"sku": "10294", "price": "63999.00",
                      "compare_at_price": None, "available": True}]}]}
    row = parse_products(payload, "official", "https://shop.test", TODAY)[0]
    assert row.url == "https://shop.test/products/titanic-10294"


def test_garbage_payload_yields_no_rows_and_does_not_raise():
    assert parse_products({}, "official", "https://x.test", TODAY) == []
    assert parse_products({"products": None}, "official", "https://x.test", TODAY) == []


def test_unparseable_price_is_skipped_not_crashed():
    payload = {"products": [{
        "title": "Broken", "vendor": "LEGO", "handle": "broken",
        "variants": [{"sku": "10294", "price": "ask us",
                      "compare_at_price": None, "available": True}]}]}
    assert parse_products(payload, "official", "https://x.test", TODAY) == []


def test_non_ascii_titles_survive():
    payload = {"products": [{
        "title": "THE LORD OF THE RINGS: RIVENDELL™", "vendor": "LEGO",
        "handle": "rivendell",
        "variants": [{"sku": "10316", "price": "50399.00",
                      "compare_at_price": None, "available": True}]}]}
    row = parse_products(payload, "official", "https://x.test", TODAY)[0]
    assert row.set_number == "10316"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_shopify.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker.models'`

- [ ] **Step 3: Write models.py**

```python
"""Shared data shapes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceRow:
    """One shop's price for one set on one day."""
    date: str              # ISO YYYY-MM-DD
    shop: str
    set_number: str
    price: float
    mrp: float | None      # None when the shop publishes no list price
    in_stock: bool
    url: str
    source: str            # "feed" | "page" | "manual"
```

- [ ] **Step 4: Write shops/shopify.py**

```python
"""Reading the three Shopify shops.

Shopify publishes every product as JSON at
/collections/<name>/products.json. This is the shop's own data: no
scraping, no browser, and it does not break on a site redesign.

Always the COLLECTION endpoint -- the single-product one omits
"available".
"""
import logging

import requests

from ..models import PriceRow
from ..setnum import extract_set_number, is_lego

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36")

SHOPIFY_SHOPS: dict[str, dict] = {
    "official": {"base": "https://lego.mybrickhouse.com", "collection": "all"},
    "toycra": {"base": "https://toycra.com", "collection": "lego"},
    "funcorp": {"base": "https://www.funcorp.in", "collection": "all"},
}

MAX_PAGES = 10


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_products(payload: dict, shop: str, base_url: str,
                   today: str) -> list[PriceRow]:
    """Turn one page of Shopify JSON into rows, cheapest variant per set."""
    products = (payload or {}).get("products") or []
    best: dict[str, PriceRow] = {}

    for product in products:
        if not is_lego(product, shop):
            continue
        handle = product.get("handle", "")
        for variant in product.get("variants") or []:
            set_number = extract_set_number(variant.get("sku"))
            if not set_number:
                continue
            price = _to_float(variant.get("price"))
            if price is None or price <= 0:
                continue
            available = variant.get("available")
            row = PriceRow(
                date=today,
                shop=shop,
                set_number=set_number,
                price=price,
                mrp=_to_float(variant.get("compare_at_price")),
                # Toycra's collection lists in-stock items only and omits
                # the field, so a missing value means in stock.
                in_stock=True if available is None else bool(available),
                url=f"{base_url}/products/{handle}",
                source="feed",
            )
            current = best.get(set_number)
            if current is None or row.price < current.price:
                best[set_number] = row

    return list(best.values())


def fetch_shop(shop: str, today: str) -> list[PriceRow]:
    """Fetch every page for one shop. Returns [] on any failure."""
    spec = SHOPIFY_SHOPS[shop]
    url = f"{spec['base']}/collections/{spec['collection']}/products.json"
    best: dict[str, PriceRow] = {}

    for page in range(1, MAX_PAGES + 1):
        try:
            response = requests.get(
                url, params={"limit": 250, "page": page},
                headers={"User-Agent": UA}, timeout=30)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            log.warning("%s page %s failed: %s", shop, page, exc)
            break
        if not (payload.get("products") or []):
            break
        for row in parse_products(payload, shop, spec["base"], today):
            current = best.get(row.set_number)
            if current is None or row.price < current.price:
                best[row.set_number] = row

    return list(best.values())
```

`src/legotracker/shops/__init__.py`:
```python
"""Shop registry."""
import logging

from ..models import PriceRow
from .shopify import SHOPIFY_SHOPS, fetch_shop

log = logging.getLogger(__name__)


def fetch_all(today: str) -> tuple[list[PriceRow], list[str]]:
    """Fetch every Shopify shop. Returns (rows, names of shops that failed)."""
    rows: list[PriceRow] = []
    failed: list[str] = []
    for shop in SHOPIFY_SHOPS:
        shop_rows = fetch_shop(shop, today)
        if shop_rows:
            rows.extend(shop_rows)
        else:
            failed.append(shop)
            log.warning("no rows from %s", shop)
    return rows, failed
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_shopify.py -q
```
Expected: 13 passed

- [ ] **Step 6: Commit**

```bash
git add src/legotracker/models.py src/legotracker/shops tests/test_shopify.py
git commit -m "feat: Shopify feed reader for the three Indian shops"
```

---

### Task 4: Price history

**Files:**
- Create: `src/legotracker/history.py`, `data/.gitkeep`
- Test: `tests/test_history.py`

**Interfaces:**
- Consumes: `PriceRow` from Task 3
- Produces: `append_rows(path, rows)`, `read_rows(path) -> list[PriceRow]`, `sticky_mrp(rows, set_number) -> float | None`, `recorded_low(rows, set_number) -> float | None`, `history_days(rows, set_number) -> int`

- [ ] **Step 1: Write the failing test**

`tests/test_history.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_history.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker.history'`

- [ ] **Step 3: Write the implementation**

`src/legotracker/history.py`:
```python
"""The append-only price record.

One CSV, committed after every run. Plain text, opens in Excel,
readable in ten years. Rows are only ever added.
"""
import csv
from pathlib import Path

from .models import PriceRow

FIELDS = ["date", "shop", "set_number", "price", "mrp",
          "in_stock", "url", "source"]


def append_rows(path, rows: list[PriceRow]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists() or path.stat().st_size == 0
    with open(path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow({
                "date": row.date,
                "shop": row.shop,
                "set_number": row.set_number,
                "price": f"{row.price:.2f}",
                "mrp": "" if row.mrp is None else f"{row.mrp:.2f}",
                "in_stock": "true" if row.in_stock else "false",
                "url": row.url,
                "source": row.source,
            })


def read_rows(path) -> list[PriceRow]:
    path = Path(path)
    if not path.exists():
        return []
    out: list[PriceRow] = []
    with open(path, newline="", encoding="utf-8") as fh:
        for record in csv.DictReader(fh):
            try:
                out.append(PriceRow(
                    date=record["date"],
                    shop=record["shop"],
                    set_number=record["set_number"],
                    price=float(record["price"]),
                    mrp=float(record["mrp"]) if record["mrp"] else None,
                    in_stock=record["in_stock"] == "true",
                    url=record["url"],
                    source=record["source"],
                ))
            except (KeyError, ValueError):
                continue  # a corrupt line must not sink the whole history
    return out


def _for_set(rows: list[PriceRow], set_number: str) -> list[PriceRow]:
    return [r for r in rows if r.set_number == set_number]


def sticky_mrp(rows: list[PriceRow], set_number: str) -> float | None:
    """Highest list price ever seen; falls back to the highest price seen.

    Sticky so a shop briefly marking a set UP cannot later make the
    return to normal look like a discount.
    """
    mine = _for_set(rows, set_number)
    if not mine:
        return None
    listed = [r.mrp for r in mine if r.mrp is not None]
    return max(listed) if listed else max(r.price for r in mine)


def recorded_low(rows: list[PriceRow], set_number: str) -> float | None:
    """Cheapest in-stock price we have ever recorded for this set."""
    prices = [r.price for r in _for_set(rows, set_number) if r.in_stock]
    return min(prices) if prices else None


def history_days(rows: list[PriceRow], set_number: str) -> int:
    """How many distinct days we have data for."""
    return len({r.date for r in _for_set(rows, set_number)})
```

Create `data/.gitkeep` (empty).

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_history.py -q
```
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add src/legotracker/history.py tests/test_history.py data/.gitkeep
git commit -m "feat: append-only price history with sticky MRP"
```

---

### Task 5: The verdict rule

The heart of the tool. Read spec section 8 before starting.

**Files:**
- Create: `src/legotracker/verdict.py`
- Modify: `src/legotracker/models.py` (add `Verdict`)
- Test: `tests/test_verdict.py`

**Interfaces:**
- Consumes: thresholds dict from Task 1
- Produces:
  - `Verdict` dataclass: `label: str`, `position: float | None`, `reason: str`, `alertable: bool`
  - `judge(price, mrp, amazon_low, amazon_high, recorded_low, history_days, in_stock, stale, thresholds) -> Verdict`
  - Labels: `"BUY_NOW"`, `"GOOD"`, `"FAIR"`, `"WAIT"`, `"NEVER_DISCOUNTS"`

- [ ] **Step 1: Write the failing test**

`tests/test_verdict.py`:
```python
import pytest

from legotracker.config import load_config
from legotracker.verdict import judge

T = load_config()["thresholds"]


def j(price, mrp, lo=None, hi=None, rec=None, days=0, stock=True, stale=False):
    return judge(price=price, mrp=mrp, amazon_low=lo, amazon_high=hi,
                 recorded_low=rec, history_days=days, in_stock=stock,
                 stale=stale, thresholds=T)


# --- the eight real sets, day one (spec section 12) -----------------

@pytest.mark.parametrize("set_number,price,mrp,lo,hi,expected", [
    ("11389", 11999, 11999, 11999, 11999, "NEVER_DISCOUNTS"),
    ("10294", 63999, 63999, 57000, 98999, "GOOD"),
    ("11377", 69999, 69999, None,  None,  "WAIT"),
    ("10350", 24499, 24499, 14500, 24501, "WAIT"),
    ("11371", 24999, 24999, 24479, 25999, "NEVER_DISCOUNTS"),
    ("76269", 48999, 48999, 24501, 48021, "WAIT"),
    ("42172", 29399, 41199, 20600, 40490, "FAIR"),
    ("10316", 40399, 50399, 25200, 45392, "WAIT"),
])
def test_day_one_verdicts(set_number, price, mrp, lo, hi, expected):
    assert j(price, mrp, lo, hi, rec=price, days=0).label == expected


def test_only_titanic_is_alertable_on_day_one():
    sets = [("11389", 11999, 11999, 11999, 11999),
            ("10294", 63999, 63999, 57000, 98999),
            ("11377", 69999, 69999, None, None),
            ("10350", 24499, 24499, 14500, 24501),
            ("11371", 24999, 24999, 24479, 25999),
            ("76269", 48999, 48999, 24501, 48021),
            ("42172", 29399, 41199, 20600, 40490),
            ("10316", 40399, 50399, 25200, 45392)]
    alertable = [s for s, p, m, lo, hi in sets
                 if j(p, m, lo, hi, rec=p, days=0).alertable]
    assert alertable == ["10294"]


# --- the MRP fallback, with every Amazon figure removed -------------

def test_fallback_flags_mclaren_and_rivendell():
    assert j(29399, 41199, rec=29399, days=0).label == "GOOD"   # 29% off
    assert j(40399, 50399, rec=40399, days=0).label == "GOOD"   # 20% off


def test_fallback_is_quiet_at_full_price():
    assert j(63999, 63999, rec=63999, days=0).label == "WAIT"


def test_fallback_boundary_at_exactly_fifteen_percent():
    assert j(8500, 10000, rec=8500, days=0).label == "GOOD"     # exactly 15%
    assert j(8501, 10000, rec=8501, days=0).label == "WAIT"     # just under


# --- Review Focus item 2: degenerate ranges -------------------------

def test_equal_anchors_do_not_divide_by_zero():
    assert j(100, 100, lo=100, hi=100).label == "NEVER_DISCOUNTS"


def test_price_above_the_high_anchor_is_wait_not_a_bargain():
    v = j(60000, 48999, lo=24501, hi=48021)
    assert v.label == "WAIT"
    assert v.position > 100


def test_price_below_the_low_anchor_is_buy_now():
    v = j(20000, 41199, lo=20600, hi=40490)
    assert v.label == "BUY_NOW"
    assert v.position < 0


# --- Review Focus item 3: missing MRP -------------------------------

def test_missing_mrp_uses_the_amazon_high_as_the_top():
    assert j(26000, None, lo=20600, hi=40490).label == "FAIR"


def test_missing_mrp_and_no_amazon_data_is_unknown_not_a_crash():
    v = j(26000, None, lo=None, hi=None)
    assert v.label == "WAIT"
    assert v.alertable is False


# --- band boundaries ------------------------------------------------

def test_band_boundaries_are_inclusive_at_the_top():
    # range 0..10000 so position equals price/100
    assert j(1000, 10000, lo=0, hi=10000).label == "BUY_NOW"   # exactly 10%
    assert j(1001, 10000, lo=0, hi=10000).label == "GOOD"
    assert j(2500, 10000, lo=0, hi=10000).label == "GOOD"      # exactly 25%
    assert j(2501, 10000, lo=0, hi=10000).label == "FAIR"
    assert j(4999, 10000, lo=0, hi=10000).label == "FAIR"
    assert j(5000, 10000, lo=0, hi=10000).label == "WAIT"      # exactly 50%


# --- the rails ------------------------------------------------------

def test_out_of_stock_is_always_wait():
    v = j(20000, 41199, lo=20600, hi=40490, stock=False)
    assert v.label == "WAIT"
    assert "stock" in v.reason.lower()


def test_stale_figures_cannot_promote_only_demote():
    fresh = j(58000, 63999, lo=57000, hi=98999, stale=False)
    stale = j(58000, 63999, lo=57000, hi=98999, stale=True)
    assert fresh.label in ("BUY_NOW", "GOOD")
    assert stale.label == "FAIR"
    assert stale.alertable is False


def test_stale_figures_still_allow_a_wait():
    assert j(48999, 48999, lo=24501, hi=48021, stale=True).label == "WAIT"


def test_recorded_low_ignored_until_min_history_days():
    # 13 days: recorded low must not count, so this falls back to MRP
    assert j(50000, 100000, rec=10000, days=13).label == "GOOD"
    # 14 days: recorded low becomes the bottom anchor -> middling
    assert j(50000, 100000, rec=10000, days=14).label == "FAIR"


def test_reason_names_the_numbers_used():
    v = j(63999, 63999, lo=57000, hi=98999)
    assert "57,000" in v.reason and "98,999" in v.reason


def test_only_buy_now_and_good_are_alertable():
    assert j(1000, 10000, lo=0, hi=10000).alertable is True    # BUY_NOW
    assert j(2000, 10000, lo=0, hi=10000).alertable is True    # GOOD
    assert j(3000, 10000, lo=0, hi=10000).alertable is False   # FAIR
    assert j(9000, 10000, lo=0, hi=10000).alertable is False   # WAIT
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_verdict.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker.verdict'`

- [ ] **Step 3: Add Verdict to models.py**

Append to `src/legotracker/models.py`:
```python
@dataclass(frozen=True)
class Verdict:
    """What the tool thinks of today's price, and why."""
    label: str                 # BUY_NOW GOOD FAIR WAIT NEVER_DISCOUNTS
    position: float | None     # % of the way up the known range
    reason: str                # plain-language, goes straight into the email
    alertable: bool            # whether this is worth an email
```

- [ ] **Step 4: Write verdict.py**

```python
"""The one rule.

Where does today's price sit between the cheapest and dearest this set
is known to have been?

    top    = MRP, or the Amazon high if that is higher
    bottom = the Amazon low, or our cheapest recorded -- whichever is
             lower. Our own low only counts once we have enough days of
             history; on day one it is just today's price, which would
             collapse the range to nothing.

With no bottom anchor at all we fall back to plain percent off MRP.
"""
from .models import Verdict

ALERTABLE = {"BUY_NOW", "GOOD"}


def _money(value: float) -> str:
    return f"Rs{value:,.0f}"


def judge(price: float, mrp: float | None, amazon_low: float | None,
          amazon_high: float | None, recorded_low: float | None,
          history_days: int, in_stock: bool, stale: bool,
          thresholds: dict) -> Verdict:
    if not in_stock:
        return Verdict("WAIT", None, "out of stock", False)

    tops = [v for v in (mrp, amazon_high) if v]
    top = max(tops) if tops else None

    bottoms = [amazon_low]
    if history_days >= thresholds["min_history_days"]:
        bottoms.append(recorded_low)
    bottoms = [v for v in bottoms if v]
    bottom = min(bottoms) if bottoms else None

    # No range to speak of: fall back to percent off MRP.
    if bottom is None or top is None:
        if not mrp:
            return Verdict("WAIT", None, "no price history yet", False)
        off = (mrp - price) / mrp * 100
        label = ("GOOD" if off >= thresholds["mrp_fallback_discount_pct"]
                 else "WAIT")
        return Verdict(label, None,
                       f"{off:.0f}% off MRP (no price history yet)",
                       label in ALERTABLE and not stale)

    span = top - bottom
    if span < thresholds["narrow_range_pct"] / 100 * top:
        return Verdict(
            "NEVER_DISCOUNTS", None,
            f"price barely moves -- its whole range is only "
            f"{span / top * 100:.0f}% wide", False)

    position = (price - bottom) / span * 100
    if position <= thresholds["buy_now_pct"]:
        label = "BUY_NOW"
    elif position <= thresholds["good_pct"]:
        label = "GOOD"
    elif position < thresholds["fair_pct"]:
        label = "FAIR"
    else:
        label = "WAIT"

    # Old figures may make us more cautious, never less.
    if stale and label in ALERTABLE:
        label = "FAIR"

    reason = (f"{position:.0f}% up its range "
              f"({_money(bottom)}-{_money(top)})")
    if stale:
        reason += " -- figures are over 6 months old"

    return Verdict(label, position, reason, label in ALERTABLE)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_verdict.py -q
```
Expected: 30 passed

- [ ] **Step 6: Commit**

```bash
git add src/legotracker/verdict.py src/legotracker/models.py tests/test_verdict.py
git commit -m "feat: range-position verdict rule"
```

---

### Task 6: Amazon and pricehistory.app

**Files:**
- Create: `src/legotracker/shops/amazon.py`
- Test: `tests/test_amazon.py`

**Interfaces:**
- Consumes: `PriceRow` from Task 3
- Produces: `parse_amazon_page(html, set_number, url, today) -> PriceRow | None`, `fetch_amazon(asin, set_number, today) -> PriceRow | None`, `parse_price_history(html) -> dict | None` (keys `low`, `high`, `average`), `fetch_price_history(url) -> dict | None`

- [ ] **Step 1: Write the failing test**

`tests/test_amazon.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_amazon.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker.shops.amazon'`

- [ ] **Step 3: Write the implementation**

`src/legotracker/shops/amazon.py`:
```python
"""Amazon.in, and the free price-history site.

Both are best-effort. Amazon serves data-centre IPs a CAPTCHA, so the
cloud run often gets nothing; the local run from Abdul's Mac works. Any
failure returns None and the run continues.

Product links are supplied in watchlist.yaml, never searched for:
searching "LEGO Technic McLaren P1 42172" returned four products, none
of them the McLaren.
"""
import logging
import re

import requests

from ..models import PriceRow

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36")

PRICE_WHOLE = re.compile(r'a-price-whole">([\d,]+)')
BASIS_PRICE = re.compile(r'basisPrice[^}]{0,80}?amount\\?&quot;:(\d+)')
BLOCKED = re.compile(r"Enter the characters you see below|not a robot",
                     re.IGNORECASE)

_RUPEES = r"(?:&#8377;|₹|Rs\.?)\s*([\d,]+)"
HISTORY_FIELDS = {
    "low": re.compile(r"Lowest.{0,120}?" + _RUPEES, re.IGNORECASE | re.DOTALL),
    "high": re.compile(r"Highest.{0,120}?" + _RUPEES, re.IGNORECASE | re.DOTALL),
    "average": re.compile(r"Average.{0,120}?" + _RUPEES,
                          re.IGNORECASE | re.DOTALL),
}


def _number(text: str) -> float:
    return float(text.replace(",", ""))


def parse_amazon_page(html: str, set_number: str, url: str,
                      today: str) -> PriceRow | None:
    if not html or BLOCKED.search(html):
        return None
    price_match = PRICE_WHOLE.search(html)
    if not price_match:
        return None
    basis = BASIS_PRICE.search(html)
    return PriceRow(
        date=today,
        shop="amazon",
        set_number=set_number,
        price=_number(price_match.group(1)),
        mrp=float(basis.group(1)) if basis else None,
        in_stock=True,
        url=url,
        source="page",
    )


def fetch_amazon(asin: str, set_number: str, today: str) -> PriceRow | None:
    url = f"https://www.amazon.in/dp/{asin}"
    try:
        response = requests.get(
            url, headers={"User-Agent": UA,
                          "Accept-Language": "en-IN,en;q=0.9"}, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        log.warning("amazon %s failed: %s", asin, exc)
        return None
    return parse_amazon_page(response.text, set_number, url, today)


def parse_price_history(html: str) -> dict | None:
    """Pull low/high/average off a pricehistory.app page."""
    if not html:
        return None
    stats = {}
    for field, pattern in HISTORY_FIELDS.items():
        match = pattern.search(html)
        if not match:
            return None
        stats[field] = _number(match.group(1))
    if stats["low"] > stats["high"]:
        log.warning("price history low above high; ignoring")
        return None
    return stats


def fetch_price_history(url: str) -> dict | None:
    try:
        response = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        response.raise_for_status()
    except Exception as exc:
        log.warning("pricehistory %s failed: %s", url, exc)
        return None
    return parse_price_history(response.text)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_amazon.py -q
```
Expected: 6 passed

If `test_parses_the_real_mclaren_page` fails on `mrp`, print the fixture's
`basisPrice` context and adjust `BASIS_PRICE` to match the real escaping:
```bash
grep -o 'basisPrice.\{0,120\}' tests/fixtures/amazon_42172.html | head -2
```
The price assertion (37079.0) must pass unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/legotracker/shops/amazon.py tests/test_amazon.py
git commit -m "feat: best-effort Amazon and pricehistory.app readers"
```

---

### Task 7: Alert state and news detection

**Files:**
- Create: `src/legotracker/alerts.py`
- Test: `tests/test_alerts.py`

**Interfaces:**
- Consumes: `Verdict` from Task 5
- Produces: `load_state(path) -> dict`, `save_state(path, state)`, `is_news(set_number, verdict, price, state, today, cooldown_days) -> bool`, `record_alert(state, set_number, verdict, price, today)`, `is_absurd(price, previous_price, swing_pct) -> bool`

- [ ] **Step 1: Write the failing test**

`tests/test_alerts.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_alerts.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker.alerts'`

- [ ] **Step 3: Write the implementation**

`src/legotracker/alerts.py`:
```python
"""Deciding what is worth an email.

A tool that emails the same "lowest price!" every day gets ignored
within a fortnight. So we remember what we last said about each set and
speak only on real news.
"""
import json
from datetime import date
from pathlib import Path

from .models import Verdict


def load_state(path) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path, state: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)


def _days_between(earlier: str, later: str) -> int:
    return (date.fromisoformat(later) - date.fromisoformat(earlier)).days


RANK = {"WAIT": 0, "NEVER_DISCOUNTS": 0, "FAIR": 1, "GOOD": 2, "BUY_NOW": 3}


def is_news(set_number: str, verdict: Verdict, price: float, state: dict,
            today: str, cooldown_days: int) -> bool:
    if not verdict.alertable:
        return False
    last = state.get(set_number)
    if last is None:
        return True
    if price < last["price"]:
        return True                                   # a new low
    if RANK[verdict.label] > RANK.get(last["label"], 0):
        return True                                   # verdict improved
    return _days_between(last["date"], today) >= cooldown_days


def record_alert(state: dict, set_number: str, verdict: Verdict,
                 price: float, today: str) -> None:
    state[set_number] = {"label": verdict.label, "price": price,
                         "date": today}


def is_absurd(price: float, previous_price: float | None,
              swing_pct: float) -> bool:
    """A price that moved more than swing_pct overnight is probably a glitch."""
    if not previous_price:
        return False
    return abs(price - previous_price) / previous_price * 100 > swing_pct
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_alerts.py -q
```
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/legotracker/alerts.py tests/test_alerts.py
git commit -m "feat: alert state, cooldown and news detection"
```

---

### Task 8: Email

**Files:**
- Create: `src/legotracker/mailer.py`
- Test: `tests/test_mailer.py`

**Interfaces:**
- Consumes: `Verdict` from Task 5
- Produces: `compose(items, failed_shops, today) -> tuple[str, str]` (subject, body), `send(subject, body, config)`

`items` is a list of dicts with keys: `set_number`, `name`, `price`, `shop`, `url`, `verdict` (a `Verdict`), `sources` (int), `history_days` (int).

- [ ] **Step 1: Write the failing test**

`tests/test_mailer.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_mailer.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker.mailer'`

- [ ] **Step 3: Write the implementation**

`src/legotracker/mailer.py`:
```python
"""Composing and sending the alert email."""
import os
import smtplib
from email.message import EmailMessage

ORDER = {"BUY_NOW": 0, "GOOD": 1, "FAIR": 2, "WAIT": 3, "NEVER_DISCOUNTS": 4}
HEADLINE = {"BUY_NOW": "BUY NOW", "GOOD": "GOOD", "FAIR": "FAIR",
            "WAIT": "WAIT", "NEVER_DISCOUNTS": "never discounts"}
ALL_SHOPS = {"official", "toycra", "funcorp"}


def compose(items: list[dict], failed_shops: list[str],
            today: str) -> tuple[str | None, str | None]:
    """Build (subject, body). Returns (None, None) when there is no news."""
    if not items:
        if ALL_SHOPS.issubset(set(failed_shops)):
            return ("LEGO tracker: could not check prices today",
                    "Could not check prices today -- every shop failed.\n"
                    f"Shops tried: {', '.join(sorted(failed_shops))}\n")
        return None, None

    ranked = sorted(items, key=lambda i: (ORDER[i["verdict"].label],
                                          -i["price"]))
    best = ranked[0]
    subject = (f"LEGO: {HEADLINE[best['verdict'].label]} on "
               f"{best['name']} -- Rs{best['price']:,.0f}")

    lines = [f"Price check for {today}", ""]
    for entry in ranked:
        verdict = entry["verdict"]
        lines += [
            f"{HEADLINE[verdict.label]} -- {entry['name']} ({entry['set_number']})",
            f"  Rs{entry['price']:,.0f} at {entry['shop']}",
            f"  {verdict.reason}",
            f"  Based on: {entry['sources']} shop"
            f"{'s' if entry['sources'] != 1 else ''}, "
            f"{entry['history_days']} days of our own records",
            f"  {entry['url']}",
            "",
        ]

    if failed_shops:
        lines.append(f"(Could not reach: {', '.join(sorted(failed_shops))})")

    return subject, "\n".join(lines)


def send(subject: str, body: str, config: dict) -> None:
    """Send via SMTP. Credentials come from the environment only."""
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]
    settings = config["email"]

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings["from_addr"]
    message["To"] = settings["to"]
    message.set_content(body)

    with smtplib.SMTP(settings["smtp_host"], settings["smtp_port"],
                      timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(message)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_mailer.py -q
```
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/legotracker/mailer.py tests/test_mailer.py
git commit -m "feat: email composition and SMTP sending"
```

---

### Task 9: Wiring it together

**Files:**
- Create: `src/legotracker/cli.py`
- Test: `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: everything above
- Produces: `build_report(rows, watchlist, history, today, thresholds) -> tuple[list[dict], list[dict]]` (alertable items, all items), `main(argv=None) -> int`

- [ ] **Step 1: Write the failing test**

`tests/test_end_to_end.py`:

This is the check from spec section 12. If it passes, the tool works.

```python
import json

from legotracker.cli import build_report
from legotracker.config import load_config, load_watchlist
from legotracker.shops.shopify import parse_products

TODAY = "2026-10-04"
T = load_config()["thresholds"]

SHOPS = [("official", "official_products.json", "https://lego.mybrickhouse.com"),
         ("toycra", "toycra_products.json", "https://toycra.com"),
         ("funcorp", "funcorp_products.json", "https://www.funcorp.in")]


def todays_rows():
    rows = []
    for shop, fixture, base in SHOPS:
        payload = json.load(open(f"tests/fixtures/{fixture}"))
        rows += parse_products(payload, shop, base, TODAY)
    return rows


def verdicts(watchlist):
    _, every = build_report(todays_rows(), watchlist, [], TODAY, T)
    return {i["set_number"]: i["verdict"].label for i in every}


def test_day_one_verdicts_match_the_spec():
    assert verdicts(load_watchlist()) == {
        "10294": "GOOD",             # Titanic, near its floor
        "42172": "FAIR",             # McLaren, mid-range
        "10316": "WAIT",             # Rivendell, 60% up its range
        "10350": "WAIT",             # Tudor Corner, at its peak
        "76269": "WAIT",             # Avengers Tower, at its peak
        "11389": "NEVER_DISCOUNTS",  # flat all year
        "11371": "NEVER_DISCOUNTS",  # range only 6% wide
        "11377": "WAIT",             # no history at all
    }


def test_the_first_email_contains_exactly_titanic():
    alerts, _ = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    assert [a["set_number"] for a in alerts] == ["10294"]


def test_rivendell_is_never_recommended_on_day_one():
    # If this fails the range maths is inverted and the tool is
    # recommending the worst prices of the year.
    alerts, _ = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    assert "10316" not in {a["set_number"] for a in alerts}
    assert "76269" not in {a["set_number"] for a in alerts}


def test_without_amazon_figures_the_mrp_fallback_takes_over():
    stripped = []
    for entry in load_watchlist():
        stripped.append({k: v for k, v in entry.items()
                         if k not in ("amazon_low", "amazon_high", "seen_on")})
    labels = verdicts(stripped)
    assert labels["42172"] == "GOOD"   # 29% off MRP
    assert labels["10316"] == "GOOD"   # 20% off MRP
    assert labels["10294"] == "WAIT"   # 0% off, now invisible


def test_no_balloon_ever_reaches_a_verdict():
    _, every = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    for entry in every:
        assert entry["price"] > 1000, f"{entry['set_number']} at {entry['price']}"


def test_each_watchlist_set_appears_at_most_once():
    _, every = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    numbers = [e["set_number"] for e in every]
    assert len(numbers) == len(set(numbers))


def test_cheapest_shop_wins_for_the_mclaren():
    _, every = build_report(todays_rows(), load_watchlist(), [], TODAY, T)
    mclaren = next(e for e in every if e["set_number"] == "42172")
    assert mclaren["price"] == 29399.0
    assert mclaren["shop"] == "toycra"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/pytest tests/test_end_to_end.py -q
```
Expected: FAIL with `ModuleNotFoundError: No module named 'legotracker.cli'`

- [ ] **Step 3: Write the implementation**

`src/legotracker/cli.py`:
```python
"""Entry point: fetch, match, record, judge, alert."""
import argparse
import logging
import sys
from datetime import date, datetime

from .alerts import (is_absurd, is_news, load_state, record_alert, save_state)
from .config import load_config, load_watchlist
from .history import (append_rows, history_days, read_rows, recorded_low,
                      sticky_mrp)
from .mailer import compose, send
from .shops import fetch_all
from .shops.amazon import fetch_amazon, fetch_price_history
from .verdict import judge

log = logging.getLogger(__name__)


def _is_stale(seen_on, today: str, stale_days: int) -> bool:
    if not seen_on:
        return False
    seen = (seen_on if isinstance(seen_on, str)
            else seen_on.isoformat())
    try:
        delta = date.fromisoformat(today) - date.fromisoformat(seen)
    except ValueError:
        return False
    return delta.days > stale_days


def build_report(rows, watchlist, history, today, thresholds):
    """Judge every watchlist set. Returns (alertable items, all items)."""
    all_items, alertable = [], []

    for entry in watchlist:
        set_number = entry["set"]
        todays = [r for r in rows if r.set_number == set_number]
        if not todays:
            continue

        in_stock = [r for r in todays if r.in_stock]
        best = min(in_stock or todays, key=lambda r: r.price)

        combined = history + todays
        mrp = sticky_mrp(combined, set_number)
        previous = recorded_low(history, set_number)

        if is_absurd(best.price, previous, thresholds["absurd_swing_pct"]):
            log.warning("ignoring absurd price %s for %s", best.price,
                        set_number)
            continue

        verdict = judge(
            price=best.price,
            mrp=mrp,
            amazon_low=entry.get("amazon_low"),
            amazon_high=entry.get("amazon_high"),
            recorded_low=previous,
            history_days=history_days(history, set_number),
            in_stock=bool(in_stock),
            stale=_is_stale(entry.get("seen_on"), today,
                            thresholds["stale_days"]),
            thresholds=thresholds,
        )

        item = {
            "set_number": set_number,
            "name": entry.get("name", set_number),
            "price": best.price,
            "shop": best.shop,
            "url": best.url,
            "verdict": verdict,
            "sources": len({r.shop for r in todays}),
            "history_days": history_days(history, set_number),
        }
        all_items.append(item)
        if verdict.alertable:
            alertable.append(item)

    return alertable, all_items


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="LEGO price tracker")
    parser.add_argument("--local", action="store_true",
                        help="run from this machine (Amazon works here)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the email instead of sending it")
    args = parser.parse_args(argv)

    config = load_config()
    thresholds = config["thresholds"]
    watchlist = load_watchlist()
    today = datetime.now().date().isoformat()

    rows, failed = fetch_all(today)

    # Amazon and pricehistory.app: best effort, never fatal.
    for entry in watchlist:
        if entry.get("asin"):
            row = fetch_amazon(entry["asin"], entry["set"], today)
            if row:
                rows.append(row)
            elif args.local:
                failed.append(f"amazon:{entry['set']}")
        if entry.get("price_history_url"):
            stats = fetch_price_history(entry["price_history_url"])
            if stats:
                entry["amazon_low"] = stats["low"]
                entry["amazon_high"] = stats["high"]
                entry["seen_on"] = today

    history = read_rows(config["paths"]["prices"])
    alertable, _ = build_report(rows, watchlist, history, today, thresholds)
    append_rows(config["paths"]["prices"], rows)

    state = load_state(config["paths"]["state"])
    news = [i for i in alertable
            if is_news(i["set_number"], i["verdict"], i["price"], state,
                       today, thresholds["cooldown_days"])]

    subject, body = compose(news, failed, today)
    if subject is None:
        log.info("nothing worth an email today")
        return 0

    if args.dry_run:
        print(subject)
        print()
        print(body)
        return 0

    send(subject, body, config)
    for item in news:
        record_alert(state, item["set_number"], item["verdict"],
                     item["price"], today)
    save_state(config["paths"]["state"], state)
    log.info("emailed about %s set(s)", len(news))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/pytest tests/test_end_to_end.py -q
```
Expected: 7 passed

- [ ] **Step 5: Run the whole suite**

```bash
make test
```
Expected: all tests pass, no failures

- [ ] **Step 6: See it work for real**

```bash
.venv/bin/python -m legotracker.cli --local --dry-run
```
Expected: a printed email naming the Titanic. If Rivendell or Avengers Tower appear, stop — the range maths is inverted.

- [ ] **Step 7: Commit**

```bash
git add src/legotracker/cli.py tests/test_end_to_end.py
git commit -m "feat: CLI wiring the full fetch-judge-alert pipeline"
```

---

### Task 10: Scheduling and setup guide

**Files:**
- Create: `.github/workflows/daily.yml`, `README.md`
- Test: manual (documented below)

**Interfaces:**
- Consumes: `python -m legotracker.cli` from Task 9
- Produces: nothing other code depends on

- [ ] **Step 1: Write the workflow**

`.github/workflows/daily.yml`:
```yaml
name: Daily LEGO price check

on:
  schedule:
    - cron: "30 1 * * *"   # 07:00 IST
  workflow_dispatch:        # lets you run it by hand from the Actions tab

permissions:
  contents: write           # needed to commit price history back

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Check prices
        env:
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          PYTHONPATH: src
        run: python -m legotracker.cli

      - name: Save today's prices
        run: |
          git config user.name "lego-tracker"
          git config user.email "noreply@github.com"
          git add data/
          git diff --staged --quiet || git commit -m "data: prices for $(date +%F)"
          git push
```

- [ ] **Step 2: Write the README**

`README.md`:
```markdown
# LEGO Price Tracker

Checks LEGO prices across four Indian shops every morning and emails you
only when a set you want reaches a genuinely good price.

Quiet days mean nothing worth your attention. That silence is the point.

## What it watches

The official LEGO store (lego.mybrickhouse.com), Toycra, FunCorp, and
Amazon.in. Sets to track live in `watchlist.yaml`.

## How it decides

One rule: where does today's price sit between the cheapest and dearest
this set is known to have been?

| Position | Verdict | Emails you? |
|---|---|---|
| Bottom 10% | BUY NOW | yes |
| Bottom 25% | GOOD | yes |
| 25-50% | FAIR | no |
| Above 50% | WAIT | no |

Sets whose whole price range is under 10% wide never trigger -- they
simply do not discount.

## Setting it up

**1. Make a Gmail app password**

Google Account -> Security -> 2-Step Verification -> App passwords.
Create one for "Mail". You get a 16-character code.

**2. Add it to GitHub**

Repository -> Settings -> Secrets and variables -> Actions -> New secret:

- `SMTP_USER` -- your Gmail address
- `SMTP_PASS` -- the 16-character app password (not your real password)

**3. Turn the schedule on**

Push to GitHub. It then runs at 07:00 IST daily. To test it immediately:
Actions tab -> "Daily LEGO price check" -> Run workflow.

## Running it yourself

```bash
make setup                  # one time
make test                   # run the test suite
make check                  # check prices now (Amazon works from home)
```

Add `--dry-run` to print the email instead of sending it:

```bash
.venv/bin/python -m legotracker.cli --local --dry-run
```

## Adding a set

Add it to `watchlist.yaml`:

```yaml
- set: "10497"
  name: Galaxy Explorer
  asin: B0XXXXXXXX          # optional, from the Amazon URL
  amazon_low: 8000          # optional, from Rufus in the Amazon app
  amazon_high: 14000
  seen_on: 2026-10-04
```

Set number and name are enough to start. The Amazon figures make it
useful on day one instead of after weeks of watching -- open the set in
the Amazon app, tap "Price history", and read the low and high off the
chart.

## Where the data lives

`data/prices.csv` -- every price ever seen, append-only, committed after
each run. Opens in Excel.
```

- [ ] **Step 3: Verify the workflow file parses**

```bash
.venv/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml')); print('workflow OK')"
```
Expected: `workflow OK`

- [ ] **Step 4: Confirm the full suite still passes**

```bash
make test
```
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/daily.yml README.md
git commit -m "feat: daily GitHub Actions schedule and setup guide"
```

- [ ] **Step 6: Manual verification (needs Abdul)**

1. Push the repository to GitHub.
2. Add `SMTP_USER` and `SMTP_PASS` as repository secrets.
3. Actions tab -> Run workflow.
4. Confirm: an email arrives naming the **Titanic**, `data/prices.csv` gains
   a commit, and the run is green.
5. Run it a second time the same day and confirm **no** second email —
   the cooldown is working.

---

## Self-Review

**Spec coverage**

| Spec section | Task |
|---|---|
| 4 — Shopify sources | 3 |
| 4 — Amazon, pricehistory.app | 6 |
| 5 — SKU matching, vendor guard | 2 |
| 6 — CSV schema, sticky MRP | 4 |
| 7 — Rufus figures in watchlist | 1, 5 |
| 8 — the verdict rule | 5 |
| 8.1 — discontinued | **not implemented in v1 — see below** |
| 9 — no spam, cooldown | 7 |
| 10 — Actions, Gmail, venv | 1, 10 |
| 11 — failure handling | 3, 7, 9 |
| 12 — testing | every task; 9 for end-to-end |

**Deferred: spec section 8.1 (retirement detection).** It needs a set to
vanish from the official catalogue and stay gone for 14 consecutive days,
so it cannot fire — or be meaningfully tested — until the tool has run for
two weeks. Building it now would mean shipping untestable code. Everything
it depends on (daily catalogue snapshots in `prices.csv`) is captured from
day one, so it can be added later with real data to test against. Flagged
for Abdul rather than silently dropped.

**Type consistency.** `PriceRow` fields are identical across tasks 3, 4, 6,
9. `Verdict` is defined in task 5 and consumed unchanged in 7, 8, 9. Set
numbers are strings everywhere (enforced by a test in task 1). `thresholds`
is passed as a plain dict throughout.

**Placeholder scan.** No TBDs. Every code step carries real code; every test
step carries real assertions.
