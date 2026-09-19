"""The small sums a maker does on the back of an envelope.

Each one is arithmetic with a right answer, so each one is written out in full
and tested against the cases that catch people out: a round that does not
divide evenly, a decrease that would eat more stitches than there are, a hook
size that is not on any chart.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

# What a written pattern calls each operation, shared with the pattern writer.
WORDS = {"SC": "sc", "HDC": "hdc", "DC": "dc", "TR": "tr",
         "SC_INC": "inc", "SC2TOG": "dec"}


# --- spreading increases or decreases -------------------------------------
def spread_evenly(stitches: int, change: int, stitch: str = "SC") -> dict:
    """Add or remove stitches, spaced as evenly as the count allows.

    The part people get wrong is that it rarely divides: 50 stitches with 6
    increases is not "8 sc, inc" six times, it is two groups of eight and four
    of seven. So the groups are worked out exactly and written the way a
    pattern writes them, biggest group first.
    """
    stitches = int(stitches)
    change = int(change)
    if stitches < 1:
        raise ValueError("start from at least one stitch")
    if change == 0:
        raise ValueError("say how many stitches to add or remove")
    plain_word = WORDS.get(stitch, "sc")

    if change > 0:
        count = change
        if count > stitches:
            raise ValueError(
                f"{stitches} stitches cannot take {count} increases — one stitch can "
                f"hold one increase, so {stitches} is the most this round can add")
        plain = stitches - count
        shaping, shaping_word = "SC_INC", "inc"
        result = stitches + count
    else:
        count = -change
        if count * 2 > stitches:
            raise ValueError(
                f"{count} decreases would use {count * 2} stitches and the round only has "
                f"{stitches} — the most this round can lose is {stitches // 2}")
        plain = stitches - count * 2
        shaping, shaping_word = "SC2TOG", "dec"
        result = stitches - count

    base, extra = divmod(plain, count)
    groups = []
    if extra:
        groups.append({"plain": base + 1, "times": extra})
    if count - extra:
        groups.append({"plain": base, "times": count - extra})

    parts = []
    for group in groups:
        if group["plain"] == 0:
            piece = f"{shaping_word} x {group['times']}"
        elif group["plain"] == 1:
            piece = f"[{plain_word}, {shaping_word}] x {group['times']}"
        else:
            piece = f"[{group['plain']} {plain_word}, {shaping_word}] x {group['times']}"
        parts.append(piece)
    operations = {shaping: count}
    if plain:
        operations[stitch] = plain
    return {
        "from_stitches": stitches, "to_stitches": result,
        "change": change, "shaping_count": count, "plain_count": plain,
        "groups": groups, "even": extra == 0,
        "instruction": ", ".join(parts) + f" ({result})",
        "operations": operations,
        "note": (None if extra == 0 else
                 f"{stitches} does not divide by {count}, so {extra} group"
                 f"{'s' if extra > 1 else ''} carry one extra plain stitch. Working the "
                 "bigger groups first keeps the shaping off the start of the round."),
    }


def change_to_target(stitches: int, target: int, stitch: str = "SC") -> dict:
    """The same sum asked the other way round: get me from here to there."""
    if int(target) == int(stitches):
        raise ValueError("that is the count you already have")
    return spread_evenly(stitches, int(target) - int(stitches), stitch)


# --- gauge: stitches to centimetres and back ------------------------------
def _round_half_up(value: float) -> int:
    """Half a stitch rounds up. Python rounds half to even, which means 52.5
    stitches becomes 52 and 53.5 becomes 54 -- surprising in a tool someone
    checks by hand."""
    return int(math.floor(float(value) + 0.5))



def size_from_gauge(gauge_stitches_per_10cm: float, gauge_rows_per_10cm: float,
                    *, stitches: int | None = None, rows: int | None = None,
                    width_cm: float | None = None, height_cm: float | None = None) -> dict:
    """Both directions at once, because a maker asks it both ways.

    Counts are whole stitches, so the centimetres that come back are what the
    rounded count actually makes, not what was asked for.
    """
    if gauge_stitches_per_10cm <= 0 or gauge_rows_per_10cm <= 0:
        raise ValueError("gauge must be more than zero in both directions")
    stitch_cm = 10 / gauge_stitches_per_10cm
    row_cm = 10 / gauge_rows_per_10cm
    out = {"stitch_width_cm": round(stitch_cm, 3), "row_height_cm": round(row_cm, 3)}

    if width_cm is not None:
        wanted = float(width_cm)
        count = max(1, _round_half_up(wanted / stitch_cm))
        out["stitches"] = count
        out["stitches_exact"] = round(wanted / stitch_cm, 2)
        out["width_cm"] = round(count * stitch_cm, 2)
        out["width_off_by_cm"] = round(count * stitch_cm - wanted, 2)
    elif stitches is not None:
        out["stitches"] = int(stitches)
        out["width_cm"] = round(int(stitches) * stitch_cm, 2)

    if height_cm is not None:
        wanted = float(height_cm)
        count = max(1, _round_half_up(wanted / row_cm))
        out["rows"] = count
        out["rows_exact"] = round(wanted / row_cm, 2)
        out["height_cm"] = round(count * row_cm, 2)
        out["height_off_by_cm"] = round(count * row_cm - wanted, 2)
    elif rows is not None:
        out["rows"] = int(rows)
        out["height_cm"] = round(int(rows) * row_cm, 2)
    if "stitches" not in out and "rows" not in out:
        raise ValueError("give a measurement or a stitch count to work from")
    return out


# --- hook and needle sizes ------------------------------------------------
_SIZES_CACHE: dict = {}


def size_tables(root: Path) -> dict:
    if not _SIZES_CACHE:
        _SIZES_CACHE.update(
            json.loads((Path(root) / "data/standards/hook_needle_sizes.json").read_text()))
    return _SIZES_CACHE


def convert_size(root: Path, kind: str = "hook", *, mm: float | None = None,
                 us: str | None = None, uk: str | None = None) -> dict:
    """One size, in all three systems, from the published table.

    A size that is not on the chart is not quietly rounded into one: the
    nearest rows either side come back instead, and the answer says so.
    """
    tables = size_tables(root)
    rows = tables["crochet_hooks" if kind == "hook" else "knitting_needles"]
    match = None
    if mm is not None:
        match = next((r for r in rows if abs(r["mm"] - float(mm)) < 0.001), None)
        if match is None:
            below = [r for r in rows if r["mm"] < float(mm)]
            above = [r for r in rows if r["mm"] > float(mm)]
            return {"kind": kind, "exact": False, "asked_mm": float(mm),
                    "nearest": [below[-1] if below else None, above[0] if above else None],
                    "note": (f"{mm} mm is not a size on the chart. The sizes either side of it "
                             "are shown; hooks are sold in the sizes listed."),
                    "sources": tables["sources"]}
    elif us:
        wanted = str(us).strip().lower().replace(" ", "")
        match = next((r for r in rows if r["us"] and
                      r["us"].lower().replace(" ", "") == wanted), None)
        if match is None:
            match = next((r for r in rows if r["us"] and
                          wanted in r["us"].lower().replace(" ", "").split("-")), None)
    elif uk:
        match = next((r for r in rows if r["uk"] and r["uk"].lower() == str(uk).strip().lower()),
                     None)
    else:
        raise ValueError("give a size in millimetres, US or UK")
    if match is None:
        return {"kind": kind, "exact": False, "note": "that size is not on the chart",
                "nearest": [], "sources": tables["sources"]}
    return {"kind": kind, "exact": True, "size": match, "sources": tables["sources"],
            "note": (None if match.get("uk") else
                     "The old UK system has no number for this size — it predates it.")}


# --- units ----------------------------------------------------------------
METRES_PER_YARD = 0.9144
GRAMS_PER_OUNCE = 28.349523125


def convert_units(value: float, unit: str) -> dict:
    """Length and weight, both ways, with the exact factors."""
    value = float(value)
    unit = str(unit).lower()
    if unit in ("m", "metre", "meters", "metres"):
        return {"metres": round(value, 2), "yards": round(value / METRES_PER_YARD, 2)}
    if unit in ("yd", "yard", "yards"):
        return {"yards": round(value, 2), "metres": round(value * METRES_PER_YARD, 2)}
    if unit in ("g", "gram", "grams"):
        return {"grams": round(value, 1), "ounces": round(value / GRAMS_PER_OUNCE, 2)}
    if unit in ("oz", "ounce", "ounces"):
        return {"ounces": round(value, 2), "grams": round(value * GRAMS_PER_OUNCE, 1)}
    raise ValueError("unit must be m, yd, g or oz")


def yarn_amount(package_mass_g: float, package_length_m: float, *,
                length_m: float | None = None, mass_g: float | None = None) -> dict:
    """Length and weight of one particular yarn, converted through its own ball.

    A metre of chunky and a metre of 4-ply weigh nothing like the same, so this
    only ever answers for a stated ball.
    """
    if package_mass_g <= 0 or package_length_m <= 0:
        raise ValueError("the ball's weight and length must both be known")
    grams_per_metre = package_mass_g / package_length_m
    if length_m is not None:
        grams = float(length_m) * grams_per_metre
        return {"length_m": round(float(length_m), 2), "mass_g": round(grams, 1),
                "balls": round(float(length_m) / package_length_m, 2),
                "grams_per_metre": round(grams_per_metre, 4)}
    if mass_g is not None:
        metres = float(mass_g) / grams_per_metre
        return {"mass_g": round(float(mass_g), 1), "length_m": round(metres, 2),
                "balls": round(float(mass_g) / package_mass_g, 2),
                "grams_per_metre": round(grams_per_metre, 4)}
    raise ValueError("give a length or a weight to convert")


# --- granny square blankets -----------------------------------------------
def plan_squares(target_width_cm: float, target_height_cm: float, square_cm: float,
                 *, join_cm: float = 0.0, border_cm: float = 0.0,
                 gauge_rows_per_10cm: float | None = None) -> dict:
    """How many squares, laid out how, and what that actually measures.

    A blanket is never exactly the size asked for: it is a whole number of
    squares, plus the seams, plus the border. The finished measurement comes
    back rather than the wish.
    """
    if square_cm <= 0:
        raise ValueError("a square has to have a size")
    if target_width_cm <= 0 or target_height_cm <= 0:
        raise ValueError("give the blanket a width and a height")
    inner_w = max(0.0, float(target_width_cm) - 2 * border_cm)
    inner_h = max(0.0, float(target_height_cm) - 2 * border_cm)
    pitch = float(square_cm) + float(join_cm)
    across = max(1, round((inner_w + join_cm) / pitch))
    down = max(1, round((inner_h + join_cm) / pitch))
    finished_w = across * square_cm + (across - 1) * join_cm + 2 * border_cm
    finished_h = down * square_cm + (down - 1) * join_cm + 2 * border_cm
    out = {"across": across, "down": down, "squares": across * down,
           "square_cm": float(square_cm), "join_cm": float(join_cm),
           "border_cm": float(border_cm),
           "finished_width_cm": round(finished_w, 1),
           "finished_height_cm": round(finished_h, 1),
           "off_by_width_cm": round(finished_w - float(target_width_cm), 1),
           "off_by_height_cm": round(finished_h - float(target_height_cm), 1)}
    if gauge_rows_per_10cm:
        # A granny square grows by one round on each side per round worked, and
        # round n carries 12n trebles: three per corner group, three per side
        # group. Both are the classic construction, not a guess at one.
        row_cm = 10 / float(gauge_rows_per_10cm)
        rounds = max(1, round(float(square_cm) / (2 * row_cm)))
        out["rounds_per_square"] = rounds
        out["stitches_per_square"] = 6 * rounds * (rounds + 1)
        out["square_cm_at_that_gauge"] = round(2 * rounds * row_cm, 1)
        # Round n holds 12n trebles, so it takes the 12(n-1) of the round below
        # and adds twelve: twelve increases, the rest worked plain. Written the
        # other way round it would try to consume stitches that are not there.
        out["program"] = {"initial_stitches": 12,
                          "rounds": [{"operations": {"DC": 12 * n - 24, "DC_INC": 12}}
                                     for n in range(2, rounds + 1)]}
        out["note_gauge"] = (
            f"At this gauge a square of {round(2 * rounds * row_cm, 1)} cm takes "
            f"{rounds} rounds — that is the size the squares will actually come out.")
    return out
