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

# Amazon pages carry a-price-whole all over: recommendations, "bought
# together", sponsored tiles. Only the block carrying priceToPay is the
# product's own price. Taking the first match anywhere once reported the
# Titanic at Rs2,999 -- a recommended item on an unavailable product page.
MAIN_PRICE = re.compile(
    r'priceToPay.{0,400}?a-price-whole"?>([\d,]+)', re.DOTALL)
UNAVAILABLE = re.compile(
    r"Currently unavailable|Temporarily out of stock|Out of Stock",
    re.IGNORECASE)

# How far from the main price block a list price may sit and still
# plausibly belong to the same product.
BASIS_WINDOW = 3000
# A list price more than this multiple of the price is another product's.
MAX_BASIS_RATIO = 3.0
# Amazon renders the list price as markup, not as a JSON amount:
#   <span ...apex-basisprice-offscreen-label">M.R.P.: &#8377;41,199.00</span>
#   <p ...> List Price: <span class="a-text-strike"> &#8377;41,199.00 </span>
_RUPEE_SIGN = r"(?:&#8377;|\u20b9|Rs\.?)"
BASIS_PRICE = re.compile(
    r"(?:M\.R\.P\.?|List Price)\s*:?\s*" + _RUPEE_SIGN + r"\s*([\d,]+)",
    re.IGNORECASE)
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
    if UNAVAILABLE.search(html):
        return None          # nothing to buy, so nothing to record
    price_match = MAIN_PRICE.search(html)
    if not price_match:
        return None          # no main price block: never guess from the page
    price = _number(price_match.group(1))

    # The list price is anchored the same way the price is. Searching the
    # whole page finds recommendation tiles, and a bogus MRP is worse than
    # no MRP: sticky_mrp would keep it as the top anchor forever.
    window = html[max(0, price_match.start() - BASIS_WINDOW):
                  price_match.end() + BASIS_WINDOW]
    basis = BASIS_PRICE.search(window)
    mrp = _number(basis.group(1)) if basis else None
    if mrp is not None and (mrp <= 0 or mrp > price * MAX_BASIS_RATIO):
        log.warning("ignoring implausible list price %s against %s", mrp, price)
        mrp = None

    return PriceRow(
        date=today,
        shop="amazon",
        set_number=set_number,
        price=price,
        mrp=mrp,
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
