"""Colour schemes made of shades you can actually buy.

A colour wheel will happily hand back #7B4FA3. No manufacturer sells #7B4FA3.
So nothing here invents a colour: the wheel is used only to work out *where* a
companion shade should sit, and then the nearest real shade from the shade
cards in the library is returned -- with its brand, product, shade name and
code, so it can be ordered -- together with how far it actually falls from that
ideal. The gap is reported rather than hidden, because a palette that looks
perfect on screen and cannot be bought is worse than no palette at all.

Distances are CIEDE2000 in CIELAB, which is the standard way of asking "would a
person call these two the same colour": roughly, under 2 is a match, under 10
is a near miss, over 25 is plainly a different colour.
"""
from __future__ import annotations

import math

# --- sRGB -> CIELAB (D65), the usual chain --------------------------------
D65 = (95.047, 100.000, 108.883)


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        raise ValueError(f"not a colour: {value!r}")
    try:
        return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"not a colour: {value!r}") from exc


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def hex_to_lab(value: str) -> tuple[float, float, float]:
    r, g, b = (_linear(c) for c in hex_to_rgb(value))
    x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) * 100
    y = (r * 0.2126729 + g * 0.7151522 + b * 0.0721750) * 100
    z = (r * 0.0193339 + g * 0.1191920 + b * 0.9503041) * 100

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29

    fx, fy, fz = f(x / D65[0]), f(y / D65[1]), f(z / D65[2])
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab_to_lch(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    light, a, b = lab
    return (light, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360)


def lch_to_lab(lch: tuple[float, float, float]) -> tuple[float, float, float]:
    light, chroma, hue = lch
    rad = math.radians(hue)
    return (light, chroma * math.cos(rad), chroma * math.sin(rad))


def delta_e(lab1, lab2) -> float:
    """CIEDE2000. Long, but it is the formula that matches what eyes do."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2
    avg_l = (l1 + l2) / 2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    avg_c = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(avg_c ** 7 / (avg_c ** 7 + 25 ** 7))) if avg_c else 0.0
    a1p, a2p = a1 * (1 + g), a2 * (1 + g)
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    avg_cp = (c1p + c2p) / 2
    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0.0
    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    else:
        dhp = h2p - h1p - 360 if h2p > h1p else h2p - h1p + 360
    dHp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2)
    if c1p * c2p == 0:
        avg_hp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        avg_hp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        avg_hp = (h1p + h2p + 360) / 2
    else:
        avg_hp = (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(avg_hp - 30))
         + 0.24 * math.cos(math.radians(2 * avg_hp))
         + 0.32 * math.cos(math.radians(3 * avg_hp + 6))
         - 0.20 * math.cos(math.radians(4 * avg_hp - 63)))
    sl = 1 + (0.015 * (avg_l - 50) ** 2) / math.sqrt(20 + (avg_l - 50) ** 2)
    sc = 1 + 0.045 * avg_cp
    sh = 1 + 0.015 * avg_cp * t
    rt = (-2 * math.sqrt(avg_cp ** 7 / (avg_cp ** 7 + 25 ** 7))
          * math.sin(math.radians(60 * math.exp(-(((avg_hp - 275) / 25) ** 2)))))
    return math.sqrt((dlp / sl) ** 2 + (dcp / sc) ** 2 + (dHp / sh) ** 2
                     + rt * (dcp / sc) * (dHp / sh))


def contrast_ratio(hex1: str, hex2: str) -> float:
    """How far apart in lightness, the way a screen measures it.

    Two shades can differ in hue and still read as one blur from across a room;
    this is what says whether a face will show up against a head.
    """
    def luminance(value: str) -> float:
        r, g, b = (_linear(c) for c in hex_to_rgb(value))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = sorted((luminance(hex1), luminance(hex2)), reverse=True)
    return (a + 0.05) / (b + 0.05)


# --- where a companion shade should sit -----------------------------------
# Hue offsets in degrees; None means "same hue, different lightness".
SCHEMES = {
    "complementary": {"name": "Complementary", "offsets": [0, 180],
                      "about": "Opposite sides of the wheel: the strongest contrast there is."},
    "analogous": {"name": "Analogous", "offsets": [0, -30, 30, -60, 60],
                  "about": "Neighbours on the wheel. Quiet, and hard to get wrong."},
    "triadic": {"name": "Triadic", "offsets": [0, 120, 240],
                "about": "Three evenly spaced hues. Lively without fighting."},
    "split": {"name": "Split complementary", "offsets": [0, 150, 210],
              "about": "The opposite hue, softened by using the two either side of it."},
    "square": {"name": "Square", "offsets": [0, 90, 180, 270],
               "about": "Four evenly spaced hues, for a piece with a lot going on."},
    "monochrome": {"name": "Shades of one colour", "offsets": None,
                   "about": "One hue, light to dark — depth without a second colour."},
    "amigurumi": {"name": "For a toy", "offsets": "amigurumi",
                  "about": ("A body colour, a pale shade for a muzzle or belly, and a dark one "
                            "for details — the three a stuffed animal usually needs.")},
}
NEUTRAL_FAMILIES = ("Neutral", "Grey")
# Below this chroma a shade has no usable hue: a wheel cannot say anything
# about grey, and pretending otherwise produces nonsense schemes.
GREY_CHROMA = 8.0


def _prepare(candidates):
    """Catalogue rows -> rows with Lab and LCh, skipping anything unreadable."""
    prepared = []
    for row in candidates:
        try:
            lab = hex_to_lab(row.get("hex"))
        except (ValueError, TypeError):
            continue
        prepared.append({**row, "_lab": lab, "_lch": lab_to_lch(lab)})
    return prepared


def _nearest(target_lab, rows, used_ids, hue_window=None, target_hue=None):
    """The real shade closest to a place on the wheel."""
    best, best_distance = None, None
    for row in rows:
        if row.get("colour_id") in used_ids:
            continue
        if hue_window is not None and target_hue is not None:
            chroma, hue = row["_lch"][1], row["_lch"][2]
            if chroma >= GREY_CHROMA:
                gap = abs((hue - target_hue + 180) % 360 - 180)
                if gap > hue_window:
                    continue
            else:
                continue           # a grey cannot stand in for a hue
        distance = delta_e(target_lab, row["_lab"])
        if best_distance is None or distance < best_distance:
            best, best_distance = row, distance
    return best, best_distance


def _public(row, ideal_hex=None, distance=None, role=None):
    out = {k: row[k] for k in ("colour_id", "yarn_id", "code", "name", "hex", "family")
           if k in row}
    out["brand"] = row.get("brand")
    out["product"] = row.get("product")
    out["role"] = role
    if ideal_hex is not None:
        out["ideal_hex"] = ideal_hex
        out["distance"] = round(distance, 1) if distance is not None else None
        out["exact"] = bool(distance is not None and distance < 2)
    return out


def _lab_to_hex(lab) -> str:
    """Only ever used to show what was aimed at, never offered as a shade."""
    light, a, b = lab
    fy = (light + 16) / 116
    fx, fz = fy + a / 500, fy - b / 200

    def finv(t: float) -> float:
        return t ** 3 if t ** 3 > 216 / 24389 else (108 / 841) * (t - 4 / 29)

    x, y, z = finv(fx) * D65[0] / 100, finv(fy) * D65[1] / 100, finv(fz) * D65[2] / 100
    r = x * 3.2404542 - y * 1.5371385 - z * 0.4985314
    g = -x * 0.9692660 + y * 1.8760108 + z * 0.0415560
    bl = x * 0.0556434 - y * 0.2040259 + z * 1.0572252

    def gamma(c: float) -> int:
        c = max(0.0, min(1.0, c))
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return int(round(c * 255))

    return "#{:02x}{:02x}{:02x}".format(gamma(r), gamma(g), gamma(bl))


def build_palette(base_row: dict, candidates: list[dict], scheme: str = "complementary",
                  count: int = 3, hue_window: float = 40.0) -> dict:
    """A scheme around one real shade, built only from other real shades."""
    if scheme not in SCHEMES:
        raise ValueError(f"unknown scheme: {scheme}")
    rows = _prepare(candidates)
    base_lab = hex_to_lab(base_row["hex"])
    base_lch = lab_to_lch(base_lab)
    used = {base_row.get("colour_id")}
    palette = [_public(base_row, role="base")]
    notes: list[str] = []
    spec = SCHEMES[scheme]
    count = max(2, min(6, int(count)))

    if base_lch[1] < GREY_CHROMA and spec["offsets"] not in (None, "amigurumi"):
        notes.append(
            f"“{base_row.get('name')}” is a neutral, and a colour wheel has nothing to say "
            "about a neutral — every hue sits equally well beside it. Shades of one colour, "
            "or the toy scheme, will give a more useful answer here.")

    if spec["offsets"] == "amigurumi":
        # A body, something pale for a muzzle or belly, something dark for details.
        # A muzzle has to *read* as a muzzle across a room, so these are chosen
        # by how far they stand off the body colour, not by nearness to an ideal
        # hue: the nearest pale green to a green body is no muzzle at all.
        light = [r for r in rows if r["_lch"][0] >= max(76.0, base_lch[0] + 20)]
        dark = [r for r in rows if r["_lch"][0] <= min(34.0, base_lch[0] - 20)]
        for pool, role, target, thin in (
                (light, "pale (muzzle, belly, inner ear)",
                 (90.0, base_lch[1] * 0.22, base_lch[2]), "pale"),
                (dark, "dark (eyes, nose, details)",
                 (16.0, base_lch[1] * 0.3, base_lch[2]), "dark")):
            found, distance = _nearest(lch_to_lab(target), pool, used)
            if found is None:
                found, distance = _nearest(lch_to_lab(target), rows, used)
                if found is not None:
                    notes.append(
                        f"No shade on this card is {thin} enough to stand off "
                        f"“{base_row.get('name')}” properly, so “{found.get('name')}” is the "
                        "closest it has — widen the search to see more.")
            if found:
                used.add(found.get("colour_id"))
                palette.append(_public(found, _lab_to_hex(lch_to_lab(target)), distance, role))
    elif spec["offsets"] is None:
        # One hue, spread across lightness -- the real card decides how far it goes.
        steps = [t for t in (92, 74, 56, 38, 20)][:count - 1]
        for light in steps:
            target = (float(light), base_lch[1], base_lch[2])
            found, distance = _nearest(lch_to_lab(target), rows, used)
            if found:
                used.add(found.get("colour_id"))
                palette.append(_public(found, _lab_to_hex(lch_to_lab(target)), distance,
                                       "lighter" if light > base_lch[0] else "darker"))
    else:
        for offset in spec["offsets"][1:count]:
            hue = (base_lch[2] + offset) % 360
            target_lab = lch_to_lab((base_lch[0], base_lch[1], hue))
            found, distance = _nearest(target_lab, rows, used, hue_window, hue)
            if found is None:                     # nothing in that part of the wheel
                found, distance = _nearest(target_lab, rows, used)
                if found is not None:
                    notes.append(
                        f"Nothing on this card sits near {round(hue)}° on the wheel, so "
                        f"“{found.get('name')}” is the closest it gets — not a true "
                        f"{spec['name'].lower()} partner.")
            if found:
                used.add(found.get("colour_id"))
                palette.append(_public(found, _lab_to_hex(target_lab), distance,
                                       f"{offset:+}° on the wheel"))

    for entry in palette[1:]:
        if entry.get("distance") is not None and entry["distance"] > 25:
            notes.append(f"“{entry['name']}” is a long way from the ideal for its place in the "
                         "scheme; the card simply has nothing closer.")
    pairs = []
    for i, first in enumerate(palette):
        for second in palette[i + 1:]:
            difference = delta_e(hex_to_lab(first["hex"]), hex_to_lab(second["hex"]))
            pairs.append({"a": first["name"], "b": second["name"],
                          "difference": round(difference, 1),
                          "contrast": round(contrast_ratio(first["hex"], second["hex"]), 2)})
    # Shades of one colour are *meant* to sit close together, so only warn there
    # when two of them are genuinely indistinguishable.
    threshold = 6 if scheme == "monochrome" else 12
    muddy = [p for p in pairs if p["difference"] < threshold]
    for pair in muddy:
        notes.append(f"“{pair['a']}” and “{pair['b']}” are close enough to read as one colour "
                     "in stitches — fine for a subtle stripe, no good for a face.")
    return {"scheme": scheme, "scheme_name": spec["name"], "about": spec["about"],
            "base": palette[0], "palette": palette, "pairs": pairs, "notes": notes}
