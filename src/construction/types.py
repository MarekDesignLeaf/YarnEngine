"""How a piece is built — and what its stitch counts therefore mean.

The consumption engine only ever needs operation counts, so it does not care
whether a piece is a stuffed head or a sleeve. What does care is everything
around it: a stitch count is a circumference on one piece and a width on
another, "round 1" is a magic ring here and a cast-on there, and 60 stitches
is 30 cm across flat but 19 cm of diameter in the round. Those differences
are the whole reason the app has only been able to make toys.

So a construction is named here once, and the rest of the app asks it rather
than assuming. Adding a way of building something is adding an entry, not
rewriting the engine.

Nothing in here invents a measurement the gauge cannot support: where a
construction's finished size depends on something the stitch counts do not
know -- how hard a tube is stuffed, how a shawl is blocked -- it says so
instead of returning a confident number.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Construction:
    id: str
    name: str
    about: str
    worked: str                 # "round" | "rows"
    start: str                  # magic_ring | ring_of_stitches | foundation_row | motif | held
    stitches_are: str           # "circumference" | "width" | "motif" | "mixed"
    shaping: str                # "anywhere" | "edges" | "none"
    preview: str                # revolution | tube | panel | outline | tiles | none
    crafts: tuple = ("crochet", "knitting")
    examples: tuple = ()
    start_label: str = "Round 1"
    row_word: str = "round"
    closed_start: bool = False
    notes: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "about": self.about, "worked": self.worked,
                "start": self.start, "start_label": self.start_label, "row_word": self.row_word,
                "stitches_are": self.stitches_are, "shaping": self.shaping,
                "preview": self.preview, "crafts": list(self.crafts),
                "examples": list(self.examples), "closed_start": self.closed_start,
                "notes": list(self.notes)}


CONSTRUCTIONS: dict[str, Construction] = {
    "round_closed": Construction(
        id="round_closed", name="In the round, from a magic ring",
        about=("Worked in a spiral from a magic ring, so the piece starts closed. The stitch "
               "count is the circumference at that point."),
        worked="round", start="magic_ring", stitches_are="circumference", shaping="anywhere",
        preview="revolution", examples=("amigurumi", "a hat crown", "a ball", "a bag base"),
        start_label="Magic ring", row_word="round", closed_start=True,
        notes=("The diameter is worked out from the circumference, which assumes the piece is "
               "roughly round in section — true of a stuffed toy, less so of a tube pressed flat.",)),
    "round_open": Construction(
        id="round_open", name="In the round, as a tube",
        about=("Worked round and round from a ring of stitches that is already there — a chain "
               "joined into a ring, or a cast-on. Open at both ends."),
        worked="round", start="ring_of_stitches", stitches_are="circumference", shaping="anywhere",
        preview="tube", examples=("a sleeve", "a sock leg", "a cowl", "a bag body", "a hat brim"),
        start_label="Starting ring", row_word="round"),
    "flat_rows": Construction(
        id="flat_rows", name="In rows, straight",
        about=("Worked in rows from a foundation row. The stitch count is the width, and it "
               "stays the same all the way up."),
        worked="rows", start="foundation_row", stitches_are="width", shaping="none",
        preview="panel", examples=("a blanket", "a scarf", "a dishcloth", "a plain panel"),
        start_label="Foundation row", row_word="row"),
    "flat_shaped": Construction(
        id="flat_shaped", name="In rows, shaped as it goes",
        about=("Worked in rows, with increases or decreases changing the width as it grows — "
               "which is how a garment panel, a triangle or a shawl gets its outline."),
        worked="rows", start="foundation_row", stitches_are="width", shaping="edges",
        preview="outline", examples=("a jumper front", "a sleeve worked flat", "a shawl",
                                     "a triangle", "a raglan yoke worked flat"),
        start_label="Foundation row", row_word="row",
        notes=("Where the shaping falls inside a row is not part of the stitch counts, so the "
               "outline drawn here is the width of each row, not the exact silhouette.",)),
    "motif_joined": Construction(
        id="motif_joined", name="Motifs joined together",
        about=("One small piece worked many times and joined — the finished size comes from the "
               "layout and the seams, not from a single stitch count."),
        worked="round", start="motif", stitches_are="motif", shaping="anywhere",
        preview="tiles", examples=("a granny square blanket", "a hexagon cardigan",
                                   "a join-as-you-go throw"),
        start_label="Motif round 1", row_word="round"),
    "branched": Construction(
        id="branched", name="Split into separate pieces, or joined from them",
        about=("One round becomes several, or several become one: two legs worked into a body, a "
               "body divided into legs, a yoke, a thumb. Each piece carries on in its own right."),
        worked="rows", start="held", stitches_are="mixed", shaping="anywhere",
        preview="none",
        examples=("two legs joined into a body", "trousers worked downwards", "a yoke",
                  "a body split for armholes", "a mitten thumb"),
        start_label="Held stitches", row_word="round",
        notes=("A branched piece has no single width or circumference, so no finished size is "
               "given here — each piece has its own.",
               "Parts that are simply sewn on — ears, arms, an octopus's tentacles — are not "
               "branched at all. They are separate pieces, and nearly always should be.")),
}

DEFAULT = "round_closed"
# What the old two program types meant, so nothing that already exists changes shape.
LEGACY_PROGRAM_TYPES = {"amigurumi": "round_closed", "branch": "branched", "flat": "flat_rows"}


def get(construction_id: str | None) -> Construction:
    key = LEGACY_PROGRAM_TYPES.get(str(construction_id or ""), str(construction_id or DEFAULT))
    if key not in CONSTRUCTIONS:
        raise KeyError(construction_id)
    return CONSTRUCTIONS[key]


def listing(craft: str | None = None) -> list[dict]:
    rows = [c.as_dict() for c in CONSTRUCTIONS.values()
            if craft is None or craft in c.crafts]
    return rows


def finished_size(construction_id: str, trace: list[dict], *,
                  gauge_stitches_per_10cm: float, gauge_rows_per_10cm: float,
                  initial_stitches: int = 0, layout: dict | None = None) -> dict:
    """What the piece measures, in the terms its construction actually has.

    A closed round piece has a height and a diameter; a flat one has a width and
    a length; a branched one has neither until its branches are known, and says
    so rather than returning a number that means nothing.
    """
    construction = get(construction_id)
    if gauge_stitches_per_10cm <= 0 or gauge_rows_per_10cm <= 0:
        raise ValueError("gauge must be more than zero in both directions")
    stitch_cm = 10 / float(gauge_stitches_per_10cm)
    row_cm = 10 / float(gauge_rows_per_10cm)
    counts = [int(step.get("output_stitches") or 0) for step in (trace or [])]
    rows = len(counts)
    out: dict = {"construction": construction.id, "rows": rows, "row_word": construction.row_word,
                 "stitch_width_cm": round(stitch_cm, 3), "row_height_cm": round(row_cm, 3),
                 "notes": list(construction.notes)}

    if construction.id == "branched":
        out["known"] = False
        out["summary"] = "no single measurement — each branch has its own"
        return out

    if construction.id == "motif_joined":
        layout = layout or {}
        across = max(1, int(layout.get("across") or 1))
        down = max(1, int(layout.get("down") or 1))
        seam = float(layout.get("join_cm") or 0)
        border = float(layout.get("border_cm") or 0)
        motif_cm = float(layout.get("motif_cm") or 0)
        if not motif_cm and counts:
            # A motif worked in rounds grows by a round on every side.
            motif_cm = 2 * rows * row_cm
        width = across * motif_cm + (across - 1) * seam + 2 * border
        height = down * motif_cm + (down - 1) * seam + 2 * border
        out.update({"known": True, "motif_cm": round(motif_cm, 1), "across": across, "down": down,
                    "motifs": across * down, "width_cm": round(width, 1),
                    "height_cm": round(height, 1),
                    "summary": f"{across * down} motifs — {round(width, 1)} × {round(height, 1)} cm"})
        return out

    if not counts:
        out["known"] = False
        out["summary"] = "nothing worked yet"
        return out

    height = rows * row_cm
    if construction.stitches_are == "circumference":
        widest = max(counts)
        narrowest = min(counts)
        diameter = widest * stitch_cm / math.pi
        # A round is one row-height of fabric *along the surface*, not one
        # row-height straight up: where a round grows fast it is going outwards
        # and the piece gets wider rather than taller. Counting every round as
        # height is what makes an app tell someone their coaster is four
        # centimetres thick.
        height = 0.0
        previous_radius = (initial_stitches or counts[0]) * stitch_cm / (2 * math.pi)
        for count in counts:
            radius = count * stitch_cm / (2 * math.pi)
            spread = abs(radius - previous_radius)
            height += math.sqrt(max(0.0, row_cm ** 2 - spread ** 2))
            previous_radius = radius
        # A piece whose height is a fraction of its width is a circle with a
        # little curl in it, not a shape with a height worth quoting.
        lies_flat = height < max(row_cm * 1.5, diameter * 0.15)
        out.update({"known": True, "height_cm": round(height, 1),
                    "height_if_stacked_cm": round(rows * row_cm, 1),
                    "diameter_cm": round(diameter, 1),
                    "circumference_cm": round(widest * stitch_cm, 1),
                    "narrowest_diameter_cm": round(narrowest * stitch_cm / math.pi, 1),
                    "lies_flat": lies_flat,
                    "summary": (f"≈ {round(diameter, 1)} cm across" if lies_flat else
                                f"≈ {round(height, 1)} × {round(diameter, 1)} cm")})
        if lies_flat:
            out["notes"] = list(out["notes"]) + [
                "Every round on this piece grows fast enough to lie flat, so it is a circle "
                "rather than a shape with a height."]
        if construction.id == "round_open":
            out["summary"] = (f"≈ {round(height, 1)} cm long, "
                              f"{round(widest * stitch_cm, 1)} cm around")
        return out

    widest = max(counts)
    narrowest = min(counts)
    out.update({"known": True, "length_cm": round(height, 1),
                "width_cm": round(widest * stitch_cm, 1),
                "narrowest_width_cm": round(narrowest * stitch_cm, 1),
                "summary": f"≈ {round(widest * stitch_cm, 1)} × {round(height, 1)} cm"})
    if construction.shaping == "edges" and widest != narrowest:
        # A shaped panel has no one width, so both ends of the range are given
        # rather than picking whichever flatters the piece.
        out["summary"] = (f"≈ {round(height, 1)} cm long, "
                          f"{round(narrowest * stitch_cm, 1)}–{round(widest * stitch_cm, 1)} cm across")
        out["outline"] = [round(n * stitch_cm, 2) for n in counts]
    return out


def start_issue(construction_id: str, initial_stitches: int, first_round_consumes: int) -> dict | None:
    """The one rule a construction really does impose: how the piece begins.

    A closed start has nothing to work into, so its first round must consume
    nothing; every other start has stitches already there and must use them.
    """
    construction = get(construction_id)
    if construction.closed_start:
        # The ring is normally given as the piece's starting stitches; a piece
        # that declares none has nothing for its first round to work into.
        if initial_stitches <= 0 and first_round_consumes:
            return {"code": "CLOSED_START_HAS_NOTHING_TO_WORK_INTO",
                    "construction": construction.id,
                    "message": (f"{construction.start_label} starts from nothing, so either say "
                                f"how many stitches go into the ring, or let the first "
                                f"{construction.row_word} make them.")}
        return None
    if construction.start in ("ring_of_stitches", "foundation_row") and initial_stitches <= 0:
        return {"code": "START_STITCHES_REQUIRED", "construction": construction.id,
                "message": (f"A piece worked as “{construction.name}” starts from a "
                            f"{construction.start_label.lower()} — say how many stitches it has.")}
    return None
