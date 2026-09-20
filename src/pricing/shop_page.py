"""Reading a price off a shop's own page — only where the shop has published one.

A yarn's price in this app has always been a number somebody typed, which goes
out of date the day after it is typed and gives no way to tell. The fix is not
to scrape prices off the visible page: that is guessing, and a wrong price in a
costing sheet is worse than no price, because a maker prices a piece from it.

Every serious shop platform publishes its price as structured data, because
search engines require it — schema.org Product/Offer as JSON-LD, the same as
microdata, or Open Graph product tags. That is a *stated* price: the shop says
"this product costs 4.75 GBP" in a machine-readable field it maintains. This
module reads only those. If a page has none, the answer is "this page does not
publish its price", never a number lifted out of the markup near a pound sign.

Which is the same rule the rest of the app follows about colours, gauges and
stitch counts: use what the maker or the manufacturer stated, and say so when
there is nothing to use.
"""
from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

# Symbols a shop might price in, and what they mean. Ambiguous ones ($ is used
# by a dozen countries) resolve to the commonest reading and are flagged, since
# a price in the wrong currency is a wrong price.
SYMBOLS = {"£": "GBP", "€": "EUR", "¥": "JPY", "₹": "INR", "₽": "RUB", "R$": "BRL",
           "kr": "SEK", "Kč": "CZK", "zł": "PLN", "$": "USD", "A$": "AUD", "C$": "CAD",
           "NZ$": "NZD", "CHF": "CHF"}
AMBIGUOUS_SYMBOLS = {"$", "kr"}
# A ball of yarn is not five thousand pounds. Above this, whatever was read is
# not a price — a phone number, an order reference, a postcode in disguise.
SANE_MAXIMUM = 5000.0


def parse_amount(raw: Any) -> float | None:
    """A number out of whatever the page wrote, or nothing.

    Half the world writes 1.234,56 and the other half 1,234.56, and a shop that
    writes "4,75" means four seventy-five. The separator that comes last is the
    decimal one; a lone separator with three digits after it is thousands.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        value = float(raw)
        return value if 0 < value <= SANE_MAXIMUM else None
    text = str(raw).strip().replace("\xa0", " ")
    # Shops write ranges with a proper dash, which would otherwise be dropped
    # and glue "£4.75 – £6.00" into 4756.
    text = re.sub(r"[\u2012-\u2015\u2212]", "-", text)
    if not text:
        return None
    # Keep digits and separators; drop the currency, the spaces and the rest.
    cleaned = re.sub(r"[^\d.,-]", "", text)
    if not re.search(r"\d", cleaned):
        return None
    if cleaned.lstrip().startswith("-"):
        return None                                   # a negative price is not one
    # "4.75 - 6.00" is a range across variants: the price being offered starts
    # at the low end, and pasting the two together would read as 4756.
    if "-" in cleaned:
        cleaned = cleaned.split("-", 1)[0]
        if not re.search(r"\d", cleaned):
            return None
    last_dot, last_comma = cleaned.rfind("."), cleaned.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        # Both present: the later one is the decimal point.
        decimal_at = max(last_dot, last_comma)
        whole = re.sub(r"[.,]", "", cleaned[:decimal_at])
        fraction = re.sub(r"[^\d]", "", cleaned[decimal_at + 1:])
        cleaned = f"{whole}.{fraction}" if fraction else whole
    elif last_dot >= 0 or last_comma >= 0:
        at = max(last_dot, last_comma)
        sep = cleaned[at]
        after = cleaned[at + 1:]
        if len(after) == 3 and cleaned.count(sep) >= 1 and len(cleaned[:at].replace(sep, "")) >= 1:
            # 1.234 or 1,234 -- thousands, unless there is only one group and
            # the page is pricing in a currency with three decimals, which no
            # yarn shop is.
            cleaned = re.sub(r"[.,]", "", cleaned)
        else:
            cleaned = cleaned[:at].replace(",", "").replace(".", "") + "." + after
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if 0 < value <= SANE_MAXIMUM else None


def parse_currency(raw: Any, fallback_text: str = "") -> tuple[str | None, bool]:
    """A currency code, and whether it had to be guessed from an ambiguous symbol."""
    text = f"{'' if raw is None else raw} {fallback_text}"
    code = re.search(r"\b([A-Z]{3})\b", text)
    if code and code.group(1) in set(SYMBOLS.values()) | {"USD", "EUR", "GBP", "AUD", "CAD",
                                                          "NZD", "CHF", "SEK", "NOK", "DKK",
                                                          "PLN", "CZK", "JPY", "INR", "ZAR"}:
        return code.group(1), False
    for symbol in sorted(SYMBOLS, key=len, reverse=True):
        if symbol in text:
            return SYMBOLS[symbol], symbol in AMBIGUOUS_SYMBOLS
    return None, False


def _walk(node: Any):
    """Every dict inside a JSON-LD blob, however deeply it is nested."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _is_type(node: dict, wanted: str) -> bool:
    kind = node.get("@type") or node.get("type")
    if isinstance(kind, str):
        return kind.lower().endswith(wanted.lower())
    if isinstance(kind, list):
        return any(isinstance(k, str) and k.lower().endswith(wanted.lower()) for k in kind)
    return False


def _offers_from(node: dict) -> list[dict]:
    """Every price an Offer or AggregateOffer on this node states."""
    found: list[dict] = []
    for offer in _walk(node.get("offers")):
        if not isinstance(offer, dict):
            continue
        currency = offer.get("priceCurrency") or offer.get("priceCurrencyCode")
        availability = offer.get("availability")
        # An AggregateOffer covers a range: the low price is the one a shopper
        # would actually pay for the cheapest variant on the page.
        for key in ("price", "lowPrice", "highPrice"):
            if key not in offer:
                continue
            amount = parse_amount(offer.get(key))
            if amount is None and isinstance(offer.get(key), dict):
                amount = parse_amount(offer[key].get("value"))
            if amount is not None:
                found.append({"amount": amount, "currency": currency,
                              "availability": availability, "key": key})
                break
    return found


def from_json_ld(soup: BeautifulSoup) -> list[dict]:
    out: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = tag.string or tag.get_text() or ""
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            # Some shops emit several JSON documents in one tag, or trailing
            # commas. One unreadable block is not a reason to give up on the page.
            continue
        for node in _walk(data):
            if _is_type(node, "Product") or "offers" in node:
                for hit in _offers_from(node):
                    hit["title"] = node.get("name") if isinstance(node.get("name"), str) else None
                    hit["source"] = "the shop's product data (JSON-LD)"
                    out.append(hit)
    return out


def from_microdata(soup: BeautifulSoup) -> list[dict]:
    out: list[dict] = []
    currency_tag = soup.find(attrs={"itemprop": "priceCurrency"})
    currency = None
    if currency_tag:
        currency = currency_tag.get("content") or currency_tag.get_text(strip=True)
    for tag in soup.find_all(attrs={"itemprop": re.compile(r"^(price|lowPrice)$")}):
        amount = parse_amount(tag.get("content") or tag.get_text(strip=True))
        if amount is None:
            continue
        out.append({"amount": amount, "currency": currency, "availability": None,
                    "source": "the shop's product data (microdata)", "title": None})
    return out


def from_meta(soup: BeautifulSoup) -> list[dict]:
    def meta(*names):
        for name in names:
            tag = (soup.find("meta", attrs={"property": name})
                   or soup.find("meta", attrs={"name": name}))
            if tag and tag.get("content"):
                return tag["content"]
        return None

    amount = parse_amount(meta("product:price:amount", "og:price:amount",
                               "product:sale_price:amount", "twitter:data1"))
    if amount is None:
        return []
    currency = meta("product:price:currency", "og:price:currency",
                    "product:sale_price:currency")
    return [{"amount": amount, "currency": currency, "availability": None,
             "source": "the shop's product tags (Open Graph)", "title": None}]


def read_price(html: str, url: str = "") -> dict:
    """What this page says its product costs — or why it does not say.

    Where a page states several prices (variants, a range, a sale price beside
    the old one) the lowest is taken, because that is the one a shopper is
    being offered.
    """
    if not (html or "").strip():
        return {"found": False, "reason": "That page came back empty."}
    soup = BeautifulSoup(html, "lxml")
    hits = from_json_ld(soup) or from_microdata(soup) or from_meta(soup)
    if not hits:
        return {"found": False, "url": url,
                "reason": ("This page does not publish a price in a form that can be read "
                           "reliably, so nothing has been changed. Type the price in by hand, "
                           "or link to the product's own page rather than a category or search "
                           "page.")}
    best = min(hits, key=lambda h: h["amount"])
    page_text = soup.get_text(" ", strip=True)[:400]
    currency, guessed = parse_currency(best.get("currency"), page_text)
    out = {"found": True, "amount": round(best["amount"], 2), "currency": currency,
           "source": best.get("source"), "url": url,
           "title": best.get("title"), "prices_on_page": len(hits),
           "availability": _availability(best.get("availability")), "notes": []}
    if currency is None:
        out["notes"].append("The page did not say which currency that is, so it has been "
                            "recorded as it was found.")
    elif guessed:
        out["notes"].append(f"The page used a symbol rather than a currency code, so this is "
                            f"being read as {currency} — worth checking if the shop is not here.")
    if len(hits) > 1:
        out["notes"].append(f"The page listed {len(hits)} prices — the lowest was taken, which "
                            f"is the cheapest variant or the sale price.")
    if out["availability"] == "out of stock":
        out["notes"].append("The shop lists this as out of stock, so the price may not be one "
                            "you can pay today.")
    return out


def _availability(raw: Any) -> str | None:
    if not raw:
        return None
    text = str(raw).lower()
    if "outofstock" in text or "out_of_stock" in text or "soldout" in text:
        return "out of stock"
    if "instock" in text or "in_stock" in text:
        return "in stock"
    if "preorder" in text or "backorder" in text:
        return "on back order"
    return None
