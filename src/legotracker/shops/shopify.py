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
