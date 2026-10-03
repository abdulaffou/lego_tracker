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
        shop_rows, ok = fetch_shop(shop, today)
        rows.extend(shop_rows)
        if not ok or not shop_rows:
            failed.append(shop)
            log.warning("%s incomplete (%s rows, ok=%s)", shop,
                        len(shop_rows), ok)
    return rows, failed
