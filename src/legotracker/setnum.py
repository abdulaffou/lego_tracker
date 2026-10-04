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
