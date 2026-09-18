"""Turn the captured Yarnsmiths specification tables into yarn library records.

The input is what each product page's own "Specification" table states -- ball
weight, length, blend, needle size, tension. Nothing here is estimated: tex is
derived arithmetically from the stated mass and length, and every record is
validated against YarnRecord before it is written, so a page that changes its
layout produces a failure rather than a silently wrong yarn.

    python scripts/import_yarnsmiths.py <captured.json> [--write]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.library.yarn import YarnRecord  # noqa: E402

BRAND = "Yarnsmiths"
SOURCE_BASE = "https://www.woolwarehouse.co.uk"

# Craft Yarn Council standard weight numbers for the categories the shop uses.
CYC = {"lace": 0, "4 ply": 1, "sport": 2, "dk": 3, "aran": 4,
       "chunky": 5, "super chunky": 6, "jumbo": 7}
# CYC 7 (jumbo) is defined by needle size rather than by the shop's wording:
# a 300 g ball worked on 30 mm needles is not the same thing as "super chunky".
JUMBO_NEEDLE_MM = 15.0


def parse_mass(text: str) -> float:
    m = re.search(r"([\d.]+)\s*g", text or "", re.I)
    if not m:
        raise ValueError(f"cannot read ball weight from {text!r}")
    return float(m.group(1))


def parse_length(text: str) -> float:
    m = re.search(r"([\d.]+)\s*(?:metres|meters|m)\b", text or "", re.I)
    if not m:
        raise ValueError(f"cannot read length from {text!r}")
    return float(m.group(1))


def parse_needles(text: str) -> tuple[float | None, float | None]:
    sizes = [float(x) for x in re.findall(r"([\d.]+)\s*mm", text or "", re.I)]
    if not sizes:
        return None, None
    return min(sizes), max(sizes)


def parse_blend(text: str) -> dict[str, float]:
    """'3% Viscose97% Wool' -> {'Viscose': 3.0, 'Wool': 97.0}.

    The shop's table concatenates the parts without a separator, so the split
    is on the percentage that starts each one.
    """
    parts = re.findall(r"([\d.]+)\s*%\s*([A-Za-z][A-Za-z \-]*?)(?=[\d.]+\s*%|$)", text or "")
    if not parts:
        raise ValueError(f"cannot read blend from {text!r}")
    out: dict[str, float] = {}
    for pct, fibre in parts:
        name = " ".join(w.capitalize() for w in fibre.strip().split())
        out[name] = out.get(name, 0.0) + float(pct)
    total = sum(out.values())
    if abs(total - 100.0) > 0.05:
        raise ValueError(f"blend {text!r} totals {total}%, not 100%")
    return out


def cyc_weight(stated: str, needle_max: float | None) -> int:
    key = (stated or "").strip().lower()
    if key not in CYC:
        raise ValueError(f"unknown yarn weight category: {stated!r}")
    n = CYC[key]
    if needle_max is not None and needle_max >= JUMBO_NEEDLE_MM:
        return CYC["jumbo"]
    return n


def build(entry: dict) -> dict:
    name = entry["Yarn Name"].strip()
    code = entry["Man. Part Code"].strip()
    mass = parse_mass(entry["Ball Weight"])
    length = parse_length(entry["Length"])
    needle_min, needle_max = parse_needles(entry.get("Needle Size", ""))
    hook_min, hook_max = parse_needles(entry.get("Hook Size", ""))
    blend = parse_blend(entry["Blend"])

    bits = [f"{entry['Yarn Weight']} weight."]
    if entry.get("Knitting Tension"):
        bits.append(entry["Knitting Tension"].rstrip(".") + ".")
    if hook_min:
        bits.append(f"Hook {entry['Hook Size']}.")
    if entry.get("Shade Count"):
        bits.append(f"{entry['Shade Count']} shades.")

    record = {
        "record_type": "yarn",
        "yarn_id": f"YARNSMITHS_{re.sub(r'[^A-Z0-9]+', '_', code.upper())}",
        "brand": BRAND,
        "product": name,
        "variant": None,
        "cyc_weight": cyc_weight(entry["Yarn Weight"], needle_max),
        "package_mass_g": mass,
        "package_length_m": length,
        "fibre_composition": blend,
        "tex": mass / length * 1000.0,
        "nominal_diameter_mm": None,
        "wpi": None,
        "recommended_needle_min_mm": needle_min,
        "recommended_needle_max_mm": needle_max,
        "source_type": "manufacturer_web",
        "source_reference": SOURCE_BASE + entry["s"],
        "evidence_level": "manufacturer_declared",
        "description": " ".join(bits),
    }
    # Validate exactly as the import pipeline will.
    YarnRecord(**{k: v for k, v in record.items() if k != "record_type"})
    return record


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    entries = json.loads(Path(sys.argv[1]).read_text())
    write = "--write" in sys.argv
    out_dir = ROOT / "data/yarns"
    existing = {json.loads(p.read_text())["yarn_id"] for p in out_dir.glob("*.json")}

    built, skipped = [], []
    for e in entries:
        try:
            rec = build(e)
        except (ValueError, KeyError) as exc:
            skipped.append((e.get("Yarn Name", "?"), str(exc)))
            continue
        if rec["yarn_id"] in existing:
            skipped.append((rec["product"], "already in the library"))
            continue
        built.append(rec)

    for rec in built:
        path = out_dir / f"{rec['yarn_id']}.json"
        if write:
            path.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(built)} record(s) {'written' if write else 'ready (dry run)'}, {len(skipped)} skipped")
    for name, why in skipped:
        print(f"  skipped {name}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
