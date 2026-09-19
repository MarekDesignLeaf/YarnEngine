"""A first piece, for someone who has never used this app.

The calculator asks for a gauge, a hook, a construction, a starting stitch
count and a list of rounds. Every one of those is a fair question and all of
them together are a wall. Someone who has just learned to crochet knows two
things: what they want to make, and roughly how big. This turns those two
answers into a real piece — rounds, a written pattern, the yarn it takes — and
says plainly which parts of it are an estimate.

Where it guesses, it guesses from the Craft Yarn Council's published ranges for
the yarn's weight, and it says so. The Council's own words are that these are
guidelines and that the gauge in your pattern wins; a swatch beats both, and
the app says that too.
"""
from __future__ import annotations

import math

from src.design.shapes import rounds_for_part

# Craft Yarn Council, Standard Yarn Weight System: crochet gauge in single
# crochet over 10 cm, and the hook range for each weight.
# https://www.craftyarncouncil.com/standards/yarn-weight-system
CYC_CROCHET = {
    0: {"name": "Lace", "gauge": (32, 42), "hook_mm": (1.4, 2.25)},
    1: {"name": "Super fine", "gauge": (21, 32), "hook_mm": (2.25, 3.5)},
    2: {"name": "Fine", "gauge": (16, 20), "hook_mm": (3.5, 4.5)},
    3: {"name": "Light", "gauge": (12, 17), "hook_mm": (4.5, 5.5)},
    4: {"name": "Medium", "gauge": (11, 14), "hook_mm": (5.5, 6.5)},
    5: {"name": "Bulky", "gauge": (8, 11), "hook_mm": (6.5, 9)},
    6: {"name": "Super bulky", "gauge": (7, 9), "hook_mm": (9, 15)},
    7: {"name": "Jumbo", "gauge": (5, 6), "hook_mm": (15, 19)},
}
# Single crochet is very slightly taller than it is wide at most gauges; this
# is the ratio the app's own default gauge (20 x 22) carries.
ROWS_TO_STITCHES = 1.1
# A stuffed piece is worked tighter than the label says, or the stuffing shows
# through. This is how much tighter, as a starting point and nothing more.
FIRM_TIGHTER = 1.25
FIRM_HOOK_DROP_MM = 1.0


def suggest_gauge(cyc_weight: int | None, firm: bool = False) -> dict:
    """A hook and a gauge to start from, when no swatch has been measured."""
    band = CYC_CROCHET.get(int(cyc_weight)) if cyc_weight is not None else None
    if band is None:
        # Nothing to go on: the app's own working default, said plainly.
        return {"gauge_stitches_per_10cm": 20.0, "gauge_rows_per_10cm": 22.0,
                "hook_mm": 3.5, "known": False,
                "note": ("This yarn's weight is not recorded, so these are the app's default "
                         "figures. Measure a swatch and the piece will be right.")}
    low, high = band["gauge"]
    hook_low, hook_high = band["hook_mm"]
    stitches = (low + high) / 2
    hook = (hook_low + hook_high) / 2
    note = (f"{band['name']} yarn: the Craft Yarn Council's range is {low}–{high} stitches "
            f"per 10 cm on a {hook_low}–{hook_high} mm hook. These are guidelines — a swatch "
            "of your own beats them.")
    if firm:
        stitches *= FIRM_TIGHTER
        hook = max(2.0, hook - FIRM_HOOK_DROP_MM)
        note += (" A stuffed piece is worked tighter than that, on a smaller hook, so the "
                 "stuffing cannot show through — that is what these figures are.")
    return {"gauge_stitches_per_10cm": round(stitches, 1),
            "gauge_rows_per_10cm": round(stitches * ROWS_TO_STITCHES, 1),
            "hook_mm": round(hook * 2) / 2, "known": True, "note": note,
            "weight_name": band["name"]}


def _straight_rounds(stitches: int, count: int, stitch: str = "SC") -> list[dict]:
    return [{"operations": {stitch: int(stitches)}} for _ in range(max(0, int(count)))]


def _disc_then_sides(diameter_cm: float, height_cm: float, gauge: dict,
                     stitch: str = "SC") -> dict:
    """A flat circle worked to size, then straight up — a hat, a basket, a bag.

    This is how every beginner's hat is built, and it is honest about what it
    is: the circle decides the width, the straight rounds decide the height.
    """
    base = rounds_for_part("disc", 1.0, float(diameter_cm),
                           gauge["gauge_stitches_per_10cm"], gauge["gauge_rows_per_10cm"],
                           stitch=stitch)
    rounds = list(base["rounds"])
    around = base["final_stitches"]
    row_cm = 10 / float(gauge["gauge_rows_per_10cm"])
    rounds += _straight_rounds(around, round(float(height_cm) / row_cm), stitch)
    return {"initial_stitches": base["initial_stitches"], "rounds": rounds,
            "around": around, "base_rounds": len(base["rounds"])}


def _flat_panel(width_cm: float, length_cm: float, gauge: dict, stitch: str = "SC") -> dict:
    stitch_cm = 10 / float(gauge["gauge_stitches_per_10cm"])
    row_cm = 10 / float(gauge["gauge_rows_per_10cm"])
    across = max(2, round(float(width_cm) / stitch_cm))
    rows = max(2, round(float(length_cm) / row_cm))
    return {"initial_stitches": across, "rounds": _straight_rounds(across, rows, stitch)}


# Every project: what it is, how it is built, and what needs to be asked.
PROJECTS: dict[str, dict] = {
    "ball": {
        "name": "A ball", "also": "a toy's head, a stuffed shape",
        "about": "Worked in a spiral from a magic ring and stuffed.",
        "construction": "round_closed", "firm": True,
        "asks": [{"key": "diameter_cm", "label": "How wide across", "unit": "cm",
                  "default": 8, "min": 3, "max": 40}],
    },
    "coaster": {
        "name": "A coaster", "also": "a round mat, a bag base",
        "about": "A flat circle, worked in the round. The first thing most people finish.",
        "construction": "round_closed", "firm": False,
        "asks": [{"key": "diameter_cm", "label": "How wide across", "unit": "cm",
                  "default": 10, "min": 5, "max": 60}],
    },
    "hat": {
        "name": "A hat", "also": "a beanie",
        "about": "A flat circle for the crown, then straight down the sides.",
        "construction": "round_closed", "firm": False,
        "asks": [{"key": "head_cm", "label": "Around the head", "unit": "cm",
                  "default": 56, "min": 35, "max": 70},
                 {"key": "height_cm", "label": "How deep", "unit": "cm",
                  "default": 20, "min": 10, "max": 35}],
    },
    "basket": {
        "name": "A basket", "also": "a bowl, a plant pot cover",
        "about": "A flat circle for the base, then straight up the sides.",
        "construction": "round_closed", "firm": True,
        "asks": [{"key": "diameter_cm", "label": "How wide across", "unit": "cm",
                  "default": 16, "min": 6, "max": 50},
                 {"key": "height_cm", "label": "How tall", "unit": "cm",
                  "default": 12, "min": 3, "max": 40}],
    },
    "scarf": {
        "name": "A scarf", "also": "a wrap",
        "about": "Rows back and forth. Nothing to shape, nothing to count.",
        "construction": "flat_rows", "firm": False,
        "asks": [{"key": "width_cm", "label": "How wide", "unit": "cm",
                  "default": 20, "min": 5, "max": 60},
                 {"key": "length_cm", "label": "How long", "unit": "cm",
                  "default": 150, "min": 40, "max": 250}],
    },
    "blanket": {
        "name": "A blanket", "also": "a throw",
        "about": "Rows back and forth, the same stitch all the way.",
        "construction": "flat_rows", "firm": False,
        "asks": [{"key": "width_cm", "label": "How wide", "unit": "cm",
                  "default": 100, "min": 30, "max": 250},
                 {"key": "length_cm", "label": "How long", "unit": "cm",
                  "default": 140, "min": 30, "max": 300}],
    },
}

HAT_EASE_CM = 2.5          # a hat is worked smaller than the head, or it slides off


def build(project_id: str, answers: dict, gauge: dict, stitch: str = "SC") -> dict:
    """The piece itself: how it is built, its rounds, and what to know about it."""
    project = PROJECTS.get(str(project_id))
    if project is None:
        raise KeyError(project_id)

    def answer(key, fallback=None):
        for ask in project["asks"]:
            if ask["key"] == key:
                raw = answers.get(key, ask["default"] if fallback is None else fallback)
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    raise ValueError(f"{ask['label'].lower()} must be a number")
                if not ask["min"] <= value <= ask["max"]:
                    raise ValueError(
                        f"{ask['label']} should be between {ask['min']} and {ask['max']} "
                        f"{ask['unit']} — {value:g} is outside what this makes sense for")
                return value
        return fallback

    notes: list[str] = []
    if project_id == "ball":
        built = rounds_for_part("sphere", answer("diameter_cm"), answer("diameter_cm"),
                                gauge["gauge_stitches_per_10cm"], gauge["gauge_rows_per_10cm"],
                                stitch=stitch)
        program = {"initial_stitches": built["initial_stitches"], "rounds": built["rounds"]}
        notes.append("Stuff it firmly before the last few rounds close it up.")
    elif project_id == "coaster":
        built = rounds_for_part("disc", 1.0, answer("diameter_cm"),
                                gauge["gauge_stitches_per_10cm"], gauge["gauge_rows_per_10cm"],
                                stitch=stitch)
        program = {"initial_stitches": built["initial_stitches"], "rounds": built["rounds"]}
        notes.append("If it starts to ruffle, your rounds are growing too fast; if it cups, "
                     "too slowly. Both are normal and both are fixable by a round or two.")
    elif project_id in ("hat", "basket"):
        if project_id == "hat":
            head = answer("head_cm")
            diameter = max(5.0, (head - HAT_EASE_CM) / math.pi)
            notes.append(f"Worked {HAT_EASE_CM:g} cm smaller than the head measurement, so it "
                         "grips instead of sliding off.")
        else:
            diameter = answer("diameter_cm")
        built = _disc_then_sides(diameter, answer("height_cm"), gauge, stitch)
        program = {"initial_stitches": built["initial_stitches"], "rounds": built["rounds"]}
        notes.append(f"The first {built['base_rounds']} rounds make the flat circle; the rest "
                     "go straight up.")
        if project_id == "basket":
            notes.append("Working into the back loop only on the first straight round gives "
                         "the base a crisp edge.")
    elif project_id in ("scarf", "blanket"):
        built = _flat_panel(answer("width_cm"), answer("length_cm"), gauge, stitch)
        program = {"initial_stitches": built["initial_stitches"], "rounds": built["rounds"]}
        notes.append("Turning chains are not counted in the yarn figure; add one at the start "
                     "of each row as your pattern says.")
    else:
        raise KeyError(project_id)

    if not gauge.get("known", True):
        notes.append("No swatch has been measured, so the size is a fair estimate rather than "
                     "a promise.")
    return {"project": project_id, "name": project["name"],
            "construction": project["construction"], "program": program,
            "rounds": len(program["rounds"]) + 1, "notes": notes}
