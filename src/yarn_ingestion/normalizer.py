from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from .models import ProductCandidate, NormalizedYarn


_WEIGHT_MAP = {
    "thread": 0,
    "lace": 0,
    "light fingering": 0,
    "fingering": 1,
    "4 ply": 1,
    "4ply": 1,
    "sock": 1,
    "sport": 2,
    "5 ply": 2,
    "5ply": 2,
    "dk": 3,
    "double knitting": 3,
    "light worsted": 3,
    "worsted": 4,
    "aran": 4,
    "chunky": 5,
    "bulky": 5,
    "super chunky": 6,
    "super bulky": 6,
    "jumbo": 7,
    "roving": None,
}

_FIBRE_ALIASES = {
    "polyamide": "Nylon",
    "nylon": "Nylon",
    "polyester": "Polyester",
    "acrylic": "Acrylic",
    "premium acrylic": "Acrylic",
    "recycled acrylic": "Recycled Acrylic",
    "cotton": "Cotton",
    "organic cotton": "Organic Cotton",
    "pima cotton": "Pima Cotton",
    "wool": "Wool",
    "merino": "Merino Wool",
    "merino wool": "Merino Wool",
    "superwash merino": "Superwash Merino Wool",
    "superwash merino wool": "Superwash Merino Wool",
    "alpaca": "Alpaca",
    "baby alpaca": "Baby Alpaca",
    "mohair": "Mohair",
    "silk": "Silk",
    "mulberry silk": "Mulberry Silk",
    "cashmere": "Cashmere",
    "viscose": "Viscose",
    "linen": "Linen",
    "cupro": "Cupro",
    "metal": "Metal",
}


def _clean_space(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"\s+", " ", str(value)).strip() or None


def stable_yarn_id(source_id: str, brand: str, product: str, variant: str | None = None) -> str:
    raw = "|".join([source_id, brand, product, variant or ""]).casefold().encode("utf-8")
    return "WEB_" + hashlib.sha256(raw).hexdigest()[:20].upper()


def parse_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(float(value)):
            return float(value)
        return None
    m = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value))
    return float(m.group(0).replace(",", ".")) if m else None


def parse_mass_g(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).lower().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|grams?|grammes?|oz)\b", text)
    if not m:
        return parse_number(value) if isinstance(value, (int, float)) else None
    n = float(m.group(1))
    unit = m.group(2)
    if unit == "kg":
        return n * 1000.0
    if unit == "oz":
        return n * 28.349523125
    return n


def parse_length_m(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).lower().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(km|m|metres?|meters?|yds?|yards?)\b", text)
    if not m:
        return parse_number(value) if isinstance(value, (int, float)) else None
    n = float(m.group(1))
    unit = m.group(2)
    if unit == "km":
        return n * 1000.0
    if unit.startswith("yd") or unit.startswith("yard"):
        return n * 0.9144
    return n


def parse_needle_range(value: Any) -> tuple[float | None, float | None]:
    if value is None:
        return None, None
    text = str(value).lower().replace(",", ".")
    vals = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    if not vals:
        return None, None
    if "mm" not in text and max(vals) > 15:
        return None, None
    if len(vals) == 1:
        return vals[0], vals[0]
    return min(vals[:2]), max(vals[:2])


def parse_composition(value: Any) -> dict[str, float]:
    if isinstance(value, dict):
        out: dict[str, float] = {}
        for k, v in value.items():
            n = parse_number(v)
            if n is not None:
                out[_canonical_fibre(str(k))] = n
        return out
    if not value:
        return {}
    text = re.sub(r"\s+", " ", str(value)).strip()
    matches = re.findall(
        r"(\d+(?:[.,]\d+)?)\s*%\s*([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 '()\-]{1,55}?)(?=\s*(?:,|/|\+|;|\d+(?:[.,]\d+)?\s*%|$))",
        text,
        flags=re.IGNORECASE,
    )
    out: dict[str, float] = {}
    for pct, fibre in matches:
        fibre = re.sub(r"\s+", " ", fibre).strip(" ,;/+-")
        fibre = re.sub(r"\([^)]*\)", "", fibre).strip()
        if not fibre:
            continue
        key = _canonical_fibre(fibre)
        out[key] = out.get(key, 0.0) + float(pct.replace(",", "."))
    return out


def _canonical_fibre(value: str) -> str:
    low = re.sub(r"\s+", " ", value).strip().casefold()
    return _FIBRE_ALIASES.get(low, " ".join(w.capitalize() for w in low.split()))


def cyc_from_weight_class(value: str | None) -> int | None:
    if not value:
        return None
    text = value.casefold().replace("/", " ")
    for key, cyc in sorted(_WEIGHT_MAP.items(), key=lambda kv: len(kv[0]), reverse=True):
        if key in text:
            return cyc
    return None


def compute_tex(mass_g: float | None, length_m: float | None) -> float | None:
    if not mass_g or not length_m or mass_g <= 0 or length_m <= 0:
        return None
    return mass_g * 1000.0 / length_m


def normalize_candidate(candidate: ProductCandidate) -> NormalizedYarn:
    raw = candidate.raw
    brand = _clean_space(raw.get("brand") or candidate.brand) or candidate.brand
    product = _clean_space(raw.get("name") or candidate.product_name) or candidate.product_name
    variant = _clean_space(raw.get("variant"))
    mass = parse_mass_g(raw.get("package_mass_g") or raw.get("weight") or raw.get("mass"))
    length = parse_length_m(raw.get("package_length_m") or raw.get("length") or raw.get("meterage"))
    composition = parse_composition(raw.get("composition") or raw.get("fibre_composition"))
    weight_class = _clean_space(raw.get("weight_class") or raw.get("yarn_weight"))
    nmin, nmax = parse_needle_range(raw.get("needle") or raw.get("recommended_needle"))
    status = "current" if candidate.active_evidence.get("current") is True else "unknown"
    return NormalizedYarn(
        yarn_id=stable_yarn_id(candidate.source_id, brand, product, variant),
        brand=brand,
        product=product,
        variant=variant,
        cyc_weight=cyc_from_weight_class(weight_class),
        package_mass_g=mass,
        package_length_m=length,
        tex=compute_tex(mass, length),
        nominal_diameter_mm=parse_number(raw.get("nominal_diameter_mm")),
        wpi=parse_number(raw.get("wpi")),
        recommended_needle_min_mm=nmin,
        recommended_needle_max_mm=nmax,
        fibre_composition=composition,
        source_type="official_web",
        source_reference=candidate.source_url,
        evidence_level="manufacturer_official_page",
        status=status,
        raw_weight_class=weight_class,
        gauge_sts_10cm=parse_number(raw.get("gauge_sts_10cm")),
        gauge_rows_10cm=parse_number(raw.get("gauge_rows_10cm")),
        sku=_clean_space(raw.get("sku")),
        gtin=_clean_space(raw.get("gtin") or raw.get("gtin13") or raw.get("gtin14")),
        colour_count=int(parse_number(raw.get("colour_count"))) if parse_number(raw.get("colour_count")) is not None else None,
        care=_clean_space(raw.get("care")),
        certification=_clean_space(raw.get("certification")),
        made_in=_clean_space(raw.get("made_in")),
        raw_material_origin=_clean_space(raw.get("raw_material_origin")),
    )
