"""A described object -> the parts to make, each with its own written pattern.

The input is a plain description (what the parts are and roughly how big each
one is relative to the whole). It can come from a person or from a photo; this
module does not care, and it never takes stitch counts from that description --
those are computed from the gauge and the stated overall height.
"""
from __future__ import annotations

from .shapes import ARCHETYPES, DEFAULT_ARCHETYPE_FOR_CATEGORY, rounds_for_part

# What a written pattern calls each operation.
OP_WORDS = {
    "SC": "sc", "HDC": "hdc", "DC": "dc", "TR": "tr", "DTR": "dtr", "SLST": "sl st",
    "CH": "ch", "SC_INC": "inc", "HDC_INC": "hdc inc", "DC_INC": "dc inc",
    "SC2TOG": "dec", "HDC2TOG": "hdc dec", "DC2TOG": "dc dec",
    "SC3TOG": "sc3tog", "DC3TOG": "dc3tog",
    "SC_BLO": "sc blo", "SC_FLO": "sc flo", "HDC_BLO": "hdc blo", "DC_BLO": "dc blo",
    "FPDC": "fpdc", "BPDC": "bpdc", "PUFF3": "puff", "POPCORN5": "popcorn",
}


def _round_text(ops: dict, out_stitches: int, plain: str = "SC", closing: str = "around",
                words: dict | None = None) -> str:
    """One round, written the way patterns are written.

    A round that repeats evenly is written as a repeat -- "[3 sc, inc] x 6" --
    because that is what a crocheter counts along; anything else is listed.
    """
    # Which words to print in -- US or UK -- is the caller's to decide.
    say = dict(OP_WORDS)
    if words:
        say.update(words)
    items = [(op, n) for op, n in ops.items() if n > 0]
    if not items:
        return "-"
    if len(items) == 1:
        op, n = items[0]
        if op == plain:
            return f"{say.get(op, op.lower())} in each st {closing} ({out_stitches})"
        if op in ("SC_INC", "HDC_INC", "DC_INC"):
            return f"{say.get(op, op.lower())} in each st {closing} ({out_stitches})"
        return f"{say.get(op, op.lower())} x {n} ({out_stitches})"
    if len(items) == 2:
        # Plain stitches plus one shaping stitch: write it as a repeat, which is
        # how it is worked -- spread evenly around, with any odd stitches left
        # over worked plain at the end.
        shaping = [x for x in items if x[0] != plain]
        plains = [x for x in items if x[0] == plain]
        if len(shaping) == 1 and len(plains) == 1 and shaping[0][1] > 0:
            s_op, s_n = shaping[0]
            p_op, p_n = plains[0]
            p_word, s_word = say.get(p_op, p_op.lower()), say.get(s_op, s_op.lower())
            per, rem = divmod(p_n, s_n)
            if per == 0:                       # nothing plain between them
                body = f"{s_n} {s_word}" if s_n > 1 else s_word
            else:
                inner = f"{per} {p_word}, {s_word}" if per > 1 else f"{p_word}, {s_word}"
                body = f"[{inner}] x {s_n}" if s_n > 1 else inner
            if rem:
                body += f", {rem} {p_word}" if rem > 1 else f", {p_word}"
            return f"{body} ({out_stitches})"
    listed = ", ".join(f"{say.get(op, op.lower())} x {n}" for op, n in items)
    return f"{listed} ({out_stitches})"


def _collapse(lines: list[str]) -> list[str]:
    """Merge runs of identical rounds: R10-20: sc in each st around (54)."""
    out, i = [], 0
    while i < len(lines):
        j = i
        while j + 1 < len(lines) and lines[j + 1] == lines[i]:
            j += 1
        label = f"R{i + 1}" if j == i else f"R{i + 1}-{j + 1}"
        out.append(f"{label}: {lines[i]}")
        i = j + 1
    return out


def part_pattern(part: dict, gauge_stitches_per_10cm: float, gauge_rows_per_10cm: float,
                 initial_stitches: int = 6) -> dict:
    """One part: geometry -> rounds -> written pattern."""
    name = str(part.get("name") or part.get("category") or "Part").strip()
    category = str(part.get("category") or "").upper()
    archetype = part.get("archetype") or DEFAULT_ARCHETYPE_FOR_CATEGORY.get(category, "sphere")
    if archetype not in ARCHETYPES:
        raise ValueError(f"unknown archetype: {archetype}")
    height = float(part["height_cm"])
    width = float(part.get("width_cm") or height)
    copies = max(1, int(part.get("copies", 1)))
    stitch = str(part.get("stitch") or "SC").upper()

    built = rounds_for_part(archetype, height, width, gauge_stitches_per_10cm,
                            gauge_rows_per_10cm, initial_stitches=initial_stitches,
                            stitch=stitch)
    stuffed = bool(part.get("stuffed", archetype not in ("disc",)))
    lines = [_round_text(r["operations"], c, plain=stitch)
             for r, c in zip(built["rounds"], built["stitch_counts"])]
    written = [f"R1: {built['initial_stitches']} {OP_WORDS.get(stitch, 'sc')} in magic ring "
               f"({built['initial_stitches']})"]
    collapsed = _collapse(lines)
    # shift the collapsed numbering by one, because R1 is the magic ring round
    shifted = []
    for line in collapsed:
        label, rest = line.split(": ", 1)
        nums = label[1:].split("-")
        label = f"R{int(nums[0]) + 1}" if len(nums) == 1 else f"R{int(nums[0]) + 1}-{int(nums[1]) + 1}"
        shifted.append(f"{label}: {rest}")
    written += shifted
    if built.get("open_end"):
        written.append("Fasten off, leaving a long tail for sewing. "
                       + ("Stuff before attaching." if stuffed else "Do not stuff."))
    else:
        written.append(f"Stuff firmly, then fasten off and draw the remaining "
                       f"{built['final_stitches']} sts closed with the tail.")
    written.append(f"Finished about {built['height_cm']} cm tall and "
                   f"{built['width_cm']} cm across at this gauge.")

    return {
        "name": name,
        "category": category or None,
        "archetype": archetype,
        "copies": copies,
        "stitch": stitch,
        "height_cm": built["height_cm"],
        "width_cm": built["width_cm"],
        "initial_stitches": built["initial_stitches"],
        "rounds": built["rounds"],
        "stitch_counts": built["stitch_counts"],
        "round_count": len(built["rounds"]) + 1,   # + the magic-ring round
        "total_stitches": sum(sum(r["operations"].values()) for r in built["rounds"]),
        "profile": built["profile"],
        "written": written,
    }


# The round writer is useful outside pattern generation too: the make-mode
# reads out rounds the person typed themselves, and they should read the same.
round_text = _round_text


def build_design(spec: dict) -> dict:
    """A whole object: scale the parts to the stated height and write them out.

    spec = {
      "object": "teddy bear",
      "total_height_cm": 24,
      "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
      "initial_stitches": 6,
      "parts": [{"name","category","archetype","copies",
                 "height_fraction"|"height_cm", "width_fraction"|"width_cm"}]
    }
    Fractions are of the object's total height, which is how a photo can be
    read: proportions are measurable, absolute sizes are not.
    """
    total_h = float(spec.get("total_height_cm") or 0)
    if total_h <= 0:
        raise ValueError("total_height_cm must be positive")
    gs = float(spec.get("gauge_stitches_per_10cm") or 20)
    gr = float(spec.get("gauge_rows_per_10cm") or 22)
    initial = int(spec.get("initial_stitches") or 6)
    parts_in = spec.get("parts") or []
    if not parts_in:
        raise ValueError("at least one part is required")

    parts = []
    for p in parts_in:
        q = dict(p)
        if "height_cm" not in q:
            frac = float(q.get("height_fraction") or 0)
            if frac <= 0:
                raise ValueError(f"part '{q.get('name')}' needs height_cm or height_fraction")
            q["height_cm"] = round(total_h * frac, 3)
        if "width_cm" not in q:
            wf = q.get("width_fraction")
            q["width_cm"] = round(total_h * float(wf), 3) if wf else q["height_cm"]
        parts.append(part_pattern(q, gs, gr, initial_stitches=initial))

    return {
        "object": spec.get("object") or "amigurumi",
        "total_height_cm": round(total_h, 2),
        "gauge_stitches_per_10cm": gs,
        "gauge_rows_per_10cm": gr,
        "parts": parts,
        "piece_count": sum(p["copies"] for p in parts),
        "total_stitches": sum(p["total_stitches"] * p["copies"] for p in parts),
        "notes": spec.get("notes") or [],
    }


def _yarn_line(y: dict | None) -> str:
    """'12.3 m · 18.4 g' for a part, empty when no yarn is known."""
    if not y:
        return ""
    bits = [f"{y['length_m_total']} m"]
    if y.get("mass_g_total") is not None:
        bits.append(f"{y['mass_g_total']} g")
    return " · ".join(bits)


def written_pattern(design: dict) -> str:
    """The whole design as one written pattern, the way a book prints it."""
    out = [design["object"].upper(),
           f"Finished height about {design['total_height_cm']} cm at "
           f"{design['gauge_stitches_per_10cm']} sts / "
           f"{design['gauge_rows_per_10cm']} rows per 10 cm.",
           "Worked in continuous rounds unless stated otherwise."]
    y = design.get("yarn") or {}
    if y.get("available"):
        need = f"YARN NEEDED: {y['length_m']} m"
        if y.get("mass_g") is not None:
            need += f" ({y['mass_g']} g)"
        if y.get("yarn_name"):
            need += f" of {y['yarn_name']}"
        if y.get("packages") is not None:
            need += f" — {y['packages']} ball{'s' if y['packages'] != 1 else ''}"
            if y.get("package_length_m"):
                need += f" of {y['package_length_m']} m"
        out.append(need + f", including a {y.get('allowance_percent', 0)}% allowance.")
    out.append("")
    for p in design["parts"]:
        head = f"{p['name'].upper()} — make {p['copies']}"
        yl = _yarn_line(p.get("yarn"))
        out.append(f"{head}   [{yl}]" if yl else head)
        out += p["written"]
        out.append("")
    if design.get("notes"):
        out.append("ASSEMBLY")
        out += [f"- {n}" for n in design["notes"]]
        out.append("")
    out.append("Stitch counts and round counts are calculated from your gauge and the "
               "stated height. Check them against your own swatch before starting.")
    return "\n".join(out)
