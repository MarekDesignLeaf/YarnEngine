"""The shade catalogue every colour in the app is picked from.

Colour is never free text. A part's colour is a row in ``yarn_colours``: either
a shade from the yarn's own card, or -- until a manufacturer's card has been
captured -- a shade from the generic craft palette in
``data/colours/standard_palette.json``. When a photo is read, the model's
description of a colour ("light brown", "teal") is *matched* against that
catalogue rather than stored as written, so what the app shows is always a real
catalogue entry the user can then change to a different catalogue entry.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PALETTE_FILE = "data/colours/standard_palette.json"
PALETTE_PREFIX = "PAL_"
SHADE_CARD_DIR = "data/colours"

# Words people (and vision models) use for a colour, mapped onto the palette
# family they belong to. Used only as a last resort, when no shade name matches.
FAMILY_WORDS = {
    "white": "Neutral", "cream": "Neutral", "ivory": "Neutral", "black": "Neutral",
    "natural": "Neutral", "brown": "Brown", "tan": "Brown", "beige": "Neutral",
    "grey": "Grey", "gray": "Grey", "silver": "Grey",
    "pink": "Pink", "rose": "Pink", "magenta": "Pink",
    "orange": "Orange", "peach": "Orange", "amber": "Orange",
    "yellow": "Yellow", "gold": "Yellow", "blonde": "Yellow",
    "red": "Red", "crimson": "Red", "maroon": "Red",
    "green": "Green", "olive": "Green",
    "blue": "Blue", "turquoise": "Blue", "cyan": "Blue", "indigo": "Blue",
    "purple": "Purple", "violet": "Purple", "lilac": "Purple", "mauve": "Purple",
}
# Modifiers that say which end of a family to prefer, dark first / light first.
LIGHT_WORDS = ("light", "pale", "pastel", "soft", "baby", "off")
DARK_WORDS = ("dark", "deep", "rich", "midnight")


def load_palette(root: Path) -> list[dict]:
    """The generic palette as rows ready for ``SQLiteStore.upsert_colour``."""
    data = json.loads((Path(root) / PALETTE_FILE).read_text())
    rows = []
    for shade in data["shades"]:
        rows.append({
            "colour_id": PALETTE_PREFIX + shade["code"],
            "yarn_id": None,
            "code": shade["code"],
            "name": shade["name"],
            "hex": shade["hex"],
            "family": shade.get("family"),
            "source_type": data.get("source_type", "standard_palette"),
            "source_reference": data.get("source_reference"),
        })
    global _PALETTE_CACHE
    _PALETTE_CACHE = rows
    return rows


def import_palette(store, root: Path, now: str) -> int:
    """Idempotent: re-running keeps one row per shade and refreshes its values."""
    rows = load_palette(root)
    for row in rows:
        store.upsert_colour(row, now)
    return len(rows)


def load_shade_cards(root: Path) -> list[dict]:
    """Every captured manufacturer shade card, as catalogue rows.

    A card belongs to one yarn, so its rows carry that yarn_id and are offered
    ahead of the generic palette for it. The colour family is worked out from
    the shade's own colour rather than claimed from the maker, so the picker
    can group and sort; the name, code and hex are as captured.
    """
    rows: list[dict] = []
    for path in sorted((Path(root) / SHADE_CARD_DIR).rglob("*.json")):
        data = json.loads(path.read_text())
        if data.get("record_type") != "yarn_shade_card":
            continue
        yarn_id = data["yarn_id"]
        for shade in data["shades"]:
            rows.append({
                "colour_id": f"{yarn_id}__{re.sub(r'[^A-Za-z0-9]+', '_', shade['code'])}",
                "yarn_id": yarn_id,
                "code": shade["code"],
                "name": shade["name"],
                "hex": shade["hex"],
                "family": family_of(shade["hex"]),
                "source_type": data.get("source_type", "manufacturer_web"),
                "source_reference": data.get("source_reference"),
            })
    return rows


def import_shade_cards(store, root: Path, now: str) -> int:
    """Idempotent, like the palette: re-running refreshes each shade in place."""
    rows = load_shade_cards(root)
    for row in rows:
        store.upsert_colour(row, now)
    return len(rows)


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    h = hex_colour.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def family_of(hex_colour: str, palette: list[dict] | None = None) -> str | None:
    """Which colour family a measured shade belongs to.

    Nearest-neighbour in RGB is no good here: a dark bottle green is closer to
    black than to any green, and half the shade card would come out "Neutral".
    Hue decides the family, with saturation and lightness separating the greys
    and the browns -- which is how a person reads a shade card.
    """
    r, g, b = (v / 255.0 for v in _rgb(hex_colour))
    hi, lo = max(r, g, b), min(r, g, b)
    value, chroma = hi, hi - lo
    sat = 0.0 if hi == 0 else chroma / hi
    if chroma < 1e-6:
        hue = 0.0
    elif hi == r:
        hue = (60 * ((g - b) / chroma)) % 360
    elif hi == g:
        hue = 60 * ((b - r) / chroma) + 120
    else:
        hue = 60 * ((r - g) / chroma) + 240

    if sat < 0.20 or chroma < 0.05:
        if value > 0.85 or value < 0.14:
            return "Neutral"                # white, cream, black
        return "Neutral" if 14 <= hue < 70 else "Grey"   # warm naturals vs true greys
    if 14 <= hue < 48 and (value < 0.62 or sat < 0.55):
        return "Brown"                      # a dulled or darkened orange
    if hue < 14 or hue >= 345:
        return "Red"
    if hue < 42:
        return "Orange"
    if hue < 70:
        return "Yellow"
    if hue < 168:
        return "Green"
    if hue < 258:
        return "Blue"
    if hue < 312:
        return "Purple"
    return "Pink"


_PALETTE_CACHE: list[dict] = []


def _norm(text: str) -> str:
    return re.sub(r"[^a-z ]+", " ", (text or "").lower()).strip()


def _luma(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def match_colour(description: str | None, colours: list[dict]) -> dict | None:
    """Best catalogue entry for a described colour, or None if nothing fits.

    Never invents a shade: the return value is always one of ``colours``. Words
    that only say how light or dark something is ("light", "deep") do not by
    themselves pick a shade -- otherwise "light brown" would land on "Light
    grey" -- they steer the choice within a colour family instead.
    """
    text = _norm(description)
    if not text or not colours:
        return None
    words = set(text.split())
    modifiers = set(LIGHT_WORDS) | set(DARK_WORDS)

    # 1. the catalogue's own name, said exactly
    for c in colours:
        if _norm(c["name"]) == text:
            return c

    # 2. score every shade on how much of its name the description actually
    #    uses, counting a distinctive word ("charcoal") for more than a family
    #    word ("grey") and a modifier ("light") for nothing on its own.
    def score(c):
        name = _norm(c["name"])
        name_words = name.split()
        s = 0
        for w in name_words:
            if w not in words:
                continue
            s += 0 if w in modifiers else (1 if w in FAMILY_WORDS else 3)
        if len(name_words) > 1 and re.search(r"\b" + re.escape(name) + r"\b", text):
            s += 6
        return s

    best = max(colours, key=score)
    best_score = score(best)
    # A shade named outright wins. A match on the family word alone ("green" in
    # "dark green") is not enough while a modifier is present -- that is what
    # the family step below is for.
    modifier_used = bool(words & modifiers)
    if best_score >= 2 or (best_score > 0 and not modifier_used):
        return best

    # 3. nothing in the catalogue was named; fall back to the colour family,
    #    biased light or dark by the modifier used.
    family = next((FAMILY_WORDS[w] for w in text.split() if w in FAMILY_WORDS), None)
    same = [c for c in colours if family and (c.get("family") or "") == family]
    if not same:
        return best if best_score > 0 else None
    same.sort(key=lambda c: _luma(c["hex"]))
    if words & set(LIGHT_WORDS):
        return same[-1]
    if words & set(DARK_WORDS):
        return same[0]
    return same[len(same) // 2]
