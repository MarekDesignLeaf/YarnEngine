"""Turn the captured Yarnsmiths shade cards into per-yarn colour files.

The input is what each range's own "all colours" page lists: every shade's
code, its name, and the ball photo the shop shows for it. The hex was measured
from that photo -- the pixels of the yarn itself, with the studio background
and the extremes of shadow and highlight discarded -- so it is an observation
of the shop's own picture, not a colour invented from the shade's name. Nothing
here is estimated from a name, and a shade the capture does not cover simply is
not written.

    python scripts/import_yarnsmiths_shades.py <capture.txt> [--write]

Capture format: "#<range-page-slug>|<sku prefix>" starting each range, then
"<code>|<name>|<hex>[|<full sku>]" per shade.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BRAND = "Yarnsmiths"
SITE = "https://www.woolwarehouse.co.uk"
CAPTURED = "2026-09-18"
METHOD = ("shade name and code as listed on the range's own page; hex sampled from "
          "that shade's ball photo on the same page")


def yarns_by_slug() -> dict[str, dict]:
    """The library's Yarnsmiths records, keyed by the page they came from."""
    out = {}
    for path in sorted((ROOT / "data/yarns").glob("YARNSMITHS_*.json")):
        rec = json.loads(path.read_text())
        slug = rec["source_reference"].rsplit("/", 1)[-1]
        out[slug] = rec
    return out


def parse(text: str) -> list[dict]:
    cards, current = [], None
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("#"):
            slug, _, prefix = line[1:].partition("|")
            current = {"slug": slug, "sku_prefix": prefix, "shades": []}
            cards.append(current)
            continue
        if current is None:
            raise ValueError("a shade appeared before any range header")
        parts = line.split("|")
        if len(parts) < 3:
            raise ValueError(f"cannot read shade line: {line!r}")
        code, name, hex_value = parts[0].strip(), parts[1].strip(), parts[2].strip()
        sku = parts[3].strip() if len(parts) > 3 and parts[3].strip() else f"{current['sku_prefix']}.{code}"
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", hex_value):
            raise ValueError(f"{code} {name}: {hex_value!r} is not a colour")
        current["shades"].append({"code": code, "name": name,
                                  "hex": hex_value.lower(), "sku": sku})
    return cards


def build(card: dict, yarn: dict) -> dict:
    seen = set()
    shades = []
    for shade in card["shades"]:
        if shade["code"] in seen:
            raise ValueError(f"{yarn['yarn_id']}: shade {shade['code']} listed twice")
        seen.add(shade["code"])
        shades.append(shade)
    return {
        "record_type": "yarn_shade_card",
        "yarn_id": yarn["yarn_id"],
        "brand": BRAND,
        "product": yarn["product"],
        "source_type": "manufacturer_web",
        "source_reference": yarn["source_reference"],
        "captured": CAPTURED,
        "method": METHOD,
        "shades": shades,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cards = parse(Path(sys.argv[1]).read_text())
    write = "--write" in sys.argv
    yarns = yarns_by_slug()
    out_dir = ROOT / "data/colours/yarnsmiths"
    out_dir.mkdir(parents=True, exist_ok=True)

    written, skipped, total = 0, [], 0
    for card in cards:
        yarn = yarns.get(card["slug"])
        if yarn is None:
            skipped.append((card["slug"], "no yarn in the library came from this page"))
            continue
        record = build(card, yarn)
        total += len(record["shades"])
        if write:
            (out_dir / f"{yarn['yarn_id']}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        written += 1
    print(f"{written} shade card(s) {'written' if write else 'ready (dry run)'}, "
          f"{total} shades, {len(skipped)} skipped")
    for slug, why in skipped:
        print(f"  skipped {slug}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
