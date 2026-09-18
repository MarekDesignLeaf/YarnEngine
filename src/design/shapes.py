"""Geometry -> crochet rounds.

A piece worked in continuous rounds is a solid of revolution: each round is a
ring whose circumference is (stitches x stitch width), so its radius follows
from the stitch count, and its height from the row gauge. That is exactly what
the 3D preview draws. Here we run it the other way: given the profile a part
should have, work out the stitch count each round needs, and the increases or
decreases that get there from the previous round.

Every generated round consumes exactly what the previous round produced, and
growth is capped at doubling and shrinking at halving per round, which is what
crochet fabric actually allows without holes or puckering.
"""
from __future__ import annotations

import math

# Archetype profiles, as radius(t) in units of the part's maximum radius, with
# t running 0 -> 1 in the order the piece is worked: t=0 is the magic ring.
# That matters -- an ear is worked from its tip outwards, so its profile starts
# narrow, and generating it the other way round produces a pattern that opens
# with a decrease. Straight geometry only, no stitch counts.
ARCHETYPES: dict[str, str] = {
    "sphere": "ball, widest in the middle (head, berry, bobble)",
    "egg": "fuller at one end than the other (body, pear shape)",
    "cylinder": "even width tube (neck, muzzle, body tube)",
    "limb": "tube with a rounded tip, left open to sew on (arm, leg, tail)",
    "cone": "worked from the tip and widening (ear, horn, beak)",
    "disc": "flat round piece (base, flat ear, eye patch)",
    "dome": "half ball, open underneath (paw, cheek, shell)",
}
# Parts that finish open, to be stuffed and sewn on, rather than closed off.
OPEN_ENDED = {"limb", "cone", "disc", "dome", "cylinder"}
DEFAULT_ARCHETYPE_FOR_CATEGORY = {
    "HEAD": "sphere", "BODY": "egg", "LIMB": "limb", "ARM": "limb", "LEG": "limb",
    "PAW_FOOT": "dome", "HAND": "dome", "EAR": "cone", "HORN_ANTLER": "cone",
    "TAIL": "limb", "MUZZLE": "dome", "NECK": "cylinder", "BEAK": "cone",
    "WING": "disc", "FIN": "disc", "SHELL_ARMOR": "dome", "ACCESSORY_BODY": "cylinder",
}


def _radius_factor(archetype: str, t: float) -> float:
    """Radius at t (0 = magic ring, 1 = last round), as a fraction of max radius."""
    t = min(1.0, max(0.0, t))
    if archetype == "sphere":
        return math.sin(math.pi * t)
    if archetype == "egg":
        return math.sin(math.pi * t) * (1 - 0.22 * math.cos(math.pi * t))
    if archetype == "cylinder":                       # rounded start, then straight
        return min(1.0, math.sin(math.pi * t / 0.2)) if t < 0.1 else 1.0
    if archetype == "limb":                           # rounded tip, then straight
        return math.sin(math.pi * t / 0.24) if t < 0.12 else 0.95 + 0.05 * (1 - t)
    if archetype == "cone":                           # worked from the tip outwards
        return max(0.1, t)
    if archetype == "dome":                           # half ball, open at the rim
        return math.sin(math.pi * t / 2)
    if archetype == "disc":                           # flat circle
        return max(0.05, t)
    return math.sin(math.pi * t)


def profile_points(archetype: str, height_cm: float, width_cm: float, samples: int = 160):
    """(height_cm, radius_cm) points, bottom to top, for one part."""
    if height_cm <= 0 or width_cm <= 0:
        raise ValueError("height_cm and width_cm must be positive")
    r_max = width_cm / 2.0
    # A flat piece has no height: it grows outwards from the ring, so the
    # distance the hook travels is the radius, not a rise.
    rise = 0.0 if archetype == "disc" else height_cm
    return [
        (round(rise * (i / (samples - 1)), 4),
         round(r_max * _radius_factor(archetype, i / (samples - 1)), 4))
        for i in range(samples)
    ]


def radius_at(points, h: float) -> float:
    """Radius of the profile at height h, interpolating between points."""
    if h <= points[0][0]:
        return points[0][1]
    for i in range(1, len(points)):
        h1, r1 = points[i]
        if h <= h1:
            h0, r0 = points[i - 1]
            span = (h1 - h0) or 1.0
            return r0 + (r1 - r0) * ((h - h0) / span)
    return points[-1][1]


def _arc_lengths(points):
    """Cumulative distance travelled *along* the profile, point by point."""
    arcs = [0.0]
    for i in range(1, len(points)):
        dh = points[i][0] - points[i - 1][0]
        dr = points[i][1] - points[i - 1][1]
        arcs.append(arcs[-1] + math.hypot(dh, dr))
    return arcs


def _point_at_arc(points, arcs, s: float):
    """The (height, radius) reached after travelling s along the profile."""
    if s <= 0:
        return points[0]
    for i in range(1, len(arcs)):
        if s <= arcs[i]:
            span = (arcs[i] - arcs[i - 1]) or 1.0
            f = (s - arcs[i - 1]) / span
            return (points[i - 1][0] + (points[i][0] - points[i - 1][0]) * f,
                    points[i - 1][1] + (points[i][1] - points[i - 1][1]) * f)
    return points[-1]


def _tidy(prev: int, target: int) -> bool:
    """True when the round can be written as an even repeat, e.g. [3 sc, inc] x 6."""
    if target == prev:
        return True
    if target > prev:
        inc = target - prev
        plain = 2 * prev - target
        return plain >= 0 and plain % inc == 0
    dec = prev - target
    plain = prev - 2 * dec
    return plain >= 0 and plain % dec == 0


def _choose_target(prev: int, exact: float, lo: int, hi: int) -> int:
    """Pick the round's stitch count: closest to the geometry, and among
    near-equal options the one a pattern can state as an even repeat."""
    base = min(hi, max(lo, round(exact)))
    best, best_key = base, None
    for cand in {base, base - 1, base + 1, base - 2, base + 2}:
        if cand < lo or cand > hi or cand < 3:
            continue
        err = abs(cand - exact)
        if err > 1.5:           # never distort the shape for the sake of tidiness
            continue
        key = (round(err * 2), 0 if _tidy(prev, cand) else 1, err)
        if best_key is None or key < best_key:
            best, best_key = cand, key
    return best


def rounds_for_profile(points, gauge_stitches_per_10cm: float, gauge_rows_per_10cm: float,
                       initial_stitches: int = 6, max_rounds: int = 400,
                       stitch: str = "SC", open_end: bool = False,
                       closing_stitches: int = 6) -> dict:
    """Rounds approximating a profile at a given gauge.

    Rounds advance one row height *along the surface*, not up the vertical
    axis: at the crown of a ball the fabric spirals outwards almost flat, so
    stepping vertically would jump straight to a wide round and produce a
    pattern that starts by decreasing. Walking the profile by arc length is
    what the hook actually does, and it reproduces the familiar 6/12/18/24
    crown of a real amigurumi pattern on its own.

    Returns the same {"operations": {OP: count}} rounds the rest of the app
    uses, plus the stitch count each round ends with. The chain is consistent
    by construction: every round consumes exactly the previous round's output.
    """
    if gauge_stitches_per_10cm <= 0 or gauge_rows_per_10cm <= 0:
        raise ValueError("gauge must be positive")
    initial = max(3, int(initial_stitches))
    stitch_w = 10.0 / gauge_stitches_per_10cm
    row_h = 10.0 / gauge_rows_per_10cm
    inc_op, dec_op = f"{stitch}_INC", "SC2TOG" if stitch == "SC" else f"{stitch}2TOG"

    arcs = _arc_lengths(points)
    # The magic ring is itself a round of fabric: it already sits where the
    # profile is as wide as `initial` stitches. Start walking from there, or the
    # first worked round comes out narrower than the ring and the pattern opens
    # with a decrease.
    ring_r = initial * stitch_w / (2 * math.pi)
    s0 = 0.0
    for k in range(1, len(arcs)):
        if points[k][1] >= ring_r:
            span = (points[k][1] - points[k - 1][1]) or 1.0
            f = max(0.0, min(1.0, (ring_r - points[k - 1][1]) / span))
            s0 = arcs[k - 1] + (arcs[k] - arcs[k - 1]) * f
            break
    usable = max(0.0, arcs[-1] - s0)
    n_rounds = max(1, min(max_rounds, round(usable / row_h)))
    floor = 3 if open_end else max(3, int(closing_stitches))
    rounds, counts, prev, closed = [], [], initial, False
    for i in range(1, n_rounds + 1):
        _, r = _point_at_arc(points, arcs, s0 + i * row_h)
        exact = (2 * math.pi * r) / stitch_w
        target = _choose_target(prev, exact, max(floor, math.ceil(prev / 2)), prev * 2)
        if target < 2 or prev < 2:
            break
        # A closed piece is not decreased down to nothing: it is cinched shut
        # once the opening is small enough.
        if not open_end and target <= floor < prev:
            target = floor
            closed = True
        ops: dict[str, int] = {}
        if target > prev:
            inc = target - prev
            if prev - inc > 0:
                ops[stitch] = prev - inc
            ops[inc_op] = inc
        elif target < prev:
            dec = prev - target
            if prev - 2 * dec > 0:
                ops[stitch] = prev - 2 * dec
            ops[dec_op] = dec
        else:
            ops[stitch] = prev
        rounds.append({"operations": ops})
        counts.append(target)
        prev = target
        if closed:
            break
    return {
        "initial_stitches": initial,
        "rounds": rounds,
        "stitch_counts": counts,
        "final_stitches": prev,
        "closed": closed,
        "open_end": bool(open_end),
        "round_height_cm": round(row_h, 4),
        "stitch_width_cm": round(stitch_w, 4),
    }


def rounds_for_part(archetype: str, height_cm: float, width_cm: float,
                    gauge_stitches_per_10cm: float, gauge_rows_per_10cm: float,
                    initial_stitches: int = 6, stitch: str = "SC") -> dict:
    """Profile an archetype at a real size, then turn it into rounds."""
    if archetype not in ARCHETYPES:
        raise ValueError(f"unknown archetype: {archetype}")
    pts = profile_points(archetype, height_cm, width_cm)
    out = rounds_for_profile(pts, gauge_stitches_per_10cm, gauge_rows_per_10cm,
                             initial_stitches=initial_stitches, stitch=stitch,
                             open_end=archetype in OPEN_ENDED)
    out["archetype"] = archetype
    out["profile"] = pts
    out["height_cm"] = round(height_cm, 2)
    out["width_cm"] = round(width_cm, 2)
    return out
