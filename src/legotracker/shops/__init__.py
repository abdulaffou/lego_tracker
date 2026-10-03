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
