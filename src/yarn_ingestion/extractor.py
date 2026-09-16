from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from .models import ProductCandidate, SourceConfig

_DISCONTINUED = re.compile(
    r"\b(discontinued|discontinuing|archived|no longer available|no longer produced|out of production)\b",
    re.IGNORECASE,
)


def _walk_jsonld(obj):
    if isinstance(obj, list):
        for item in obj:
            yield from _walk_jsonld(item)
    elif isinstance(obj, dict):
        if "@graph" in obj:
            yield from _walk_jsonld(obj["@graph"])
        yield obj


def jsonld_products(soup: BeautifulSoup) -> list[dict]:
    out = []
    for tag in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = tag.string or tag.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        for obj in _walk_jsonld(parsed):
            kind = obj.get("@type")
            kinds = {str(k).casefold() for k in kind} if isinstance(kind, list) else {str(kind).casefold()}
            if "product" in kinds:
                out.append(obj)
    return out


def _brand_name(value):
    if isinstance(value, dict):
        return value.get("name")
    return value if isinstance(value, str) else None


def _offer_data(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, dict):
        return {}
    return {
        "price": value.get("price"),
        "currency": value.get("priceCurrency"),
        "availability": value.get("availability"),
        "sku": value.get("sku"),
    }


def extract_product(url: str, html: str, source: SourceConfig, discovered_via: str) -> ProductCandidate | None:
    soup = BeautifulSoup(html, "lxml")
    products = jsonld_products(soup)
    product = products[0] if products else {}
    name = product.get("name")
    if not name:
        h1 = soup.find("h1")
        name = h1.get_text(" ", strip=True) if h1 else None
    if not name:
        title = soup.title.get_text(" ", strip=True) if soup.title else None
        name = title
    if not name:
        return None

    text = soup.get_text(" ", strip=True)
    raw = {
        "name": name,
        "brand": _brand_name(product.get("brand")) or source.display_name,
        "sku": product.get("sku"),
        "gtin": product.get("gtin13") or product.get("gtin14") or product.get("gtin"),
        **_offer_data(product.get("offers")),
    }
    desc = product.get("description") or ""
    search_text = f"{desc} {text}"
    raw.update(_extract_specs(search_text))

    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    current = discovered_via.startswith("catalogue") and not _DISCONTINUED.search(page_title)
    if _DISCONTINUED.search(page_title):
        current = False
    active_evidence = {
        "current": bool(current),
        "discovered_via": discovered_via,
        "discontinued_marker": bool(_DISCONTINUED.search(page_title)),
        "availability": raw.get("availability"),
    }
    confidence = _confidence(raw, active_evidence)
    return ProductCandidate(
        source_id=source.source_id,
        brand=str(raw.get("brand") or source.display_name),
        product_name=str(name),
        source_url=url,
        discovered_via=discovered_via,
        raw=raw,
        active_evidence=active_evidence,
        confidence=confidence,
    )


def _extract_specs(text: str) -> dict:
    out = {}
    # Prefer labelled forms to reduce false extraction from unrelated page text.
    mass_patterns = [
        r"(?:ball|skein|hank|cake|weight|net weight)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(g|grams?|grammes?|kg|oz)\b",
        r"\b(\d+(?:[.,]\d+)?)\s*(g|grams?|grammes?)\s*(?:ball|skein|hank|cake)\b",
    ]
    length_patterns = [
        r"(?:length|meterage|metrage|yardage|metres|meters)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(m|metres?|meters?|yds?|yards?)\b",
        r"\b(\d+(?:[.,]\d+)?)\s*(m|metres?|meters?)\s*(?:per|/)\s*(?:ball|skein|hank|cake)\b",
    ]
    for pat in mass_patterns:
        m = re.search(pat, text, re.I)
        if m:
            out["weight"] = f"{m.group(1)} {m.group(2)}"
            break
    for pat in length_patterns:
        m = re.search(pat, text, re.I)
        if m:
            out["length"] = f"{m.group(1)} {m.group(2)}"
            break

    comp = _extract_composition(text)
    if comp:
        out["composition"] = comp

    wc = re.search(r"(?:yarn\s*weight|weight\s*category|weight)\s*[:\-]?\s*(lace|fingering|4\s*ply|sport|dk|double knitting|worsted|aran|chunky|bulky|super chunky|super bulky|jumbo)\b", text, re.I)
    if wc:
        out["weight_class"] = wc.group(1)
    needle = re.search(r"(?:needle|needles|knitting needle)\s*(?:size)?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)(?:\s*[-–to]+\s*(\d+(?:[.,]\d+)?))?\s*mm\b", text, re.I)
    if needle:
        out["needle"] = f"{needle.group(1)}-{needle.group(2)} mm" if needle.group(2) else f"{needle.group(1)} mm"
    gauge = re.search(r"(?:gauge|tension)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(?:sts|stitches).*?(?:x|by)\s*(\d+(?:[.,]\d+)?)\s*(?:rows)?.*?10\s*cm", text, re.I)
    if gauge:
        out["gauge_sts_10cm"] = gauge.group(1)
        out["gauge_rows_10cm"] = gauge.group(2)
    return out


def _extract_composition(text: str) -> str | None:
    fibre = r"(?:wool|merino(?: wool)?|alpaca|baby alpaca|cotton|organic cotton|pima cotton|acrylic|recycled acrylic|polyamide|nylon|polyester|viscose|linen|silk|mulberry silk|cashmere|mohair|cupro|metal)"
    hits = re.findall(rf"(\d+(?:[.,]\d+)?)\s*%\s*({fibre})", text, re.I)
    if not hits:
        return None
    # Use the first coherent group up to 100%, which is conservative.
    parts = []
    total = 0.0
    for pct, name in hits[:8]:
        n = float(pct.replace(",", "."))
        if total + n > 105:
            break
        parts.append(f"{pct}% {name}")
        total += n
        if 99 <= total <= 101:
            break
    return ", ".join(parts) if parts else None


def discover_links(base_url: str, html: str, source: SourceConfig) -> tuple[set[str], set[str]]:
    soup = BeautifulSoup(html, "lxml")
    products: set[str] = set()
    catalogues: set[str] = set()
    product_re = re.compile(source.product_url_regex) if source.product_url_regex else None
    exclude_re = re.compile(source.exclude_url_regex) if source.exclude_url_regex else None
    origin = urlparse(base_url).netloc
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].strip())
        p = urlparse(href)
        if p.scheme not in {"http", "https"} or p.netloc != origin:
            continue
        clean = p._replace(fragment="").geturl()
        if exclude_re and exclude_re.search(clean):
            continue
        if product_re and product_re.search(clean):
            products.add(clean)
        rel = {str(x).casefold() for x in (a.get("rel") or [])}
        label = a.get_text(" ", strip=True).casefold()
        if "next" in rel or label in {"next", "next page", ">", "›", "»"}:
            catalogues.add(clean)
    return products, catalogues


def _confidence(raw: dict, evidence: dict) -> float:
    score = 0.0
    if raw.get("name"):
        score += 0.20
    if raw.get("brand"):
        score += 0.05
    if evidence.get("current") is True:
        score += 0.25
    if raw.get("composition"):
        score += 0.15
    if raw.get("weight"):
        score += 0.15
    if raw.get("length"):
        score += 0.15
    if raw.get("sku") or raw.get("gtin"):
        score += 0.05
    return min(score, 1.0)
