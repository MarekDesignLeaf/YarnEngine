"""The same stitch, under its two names.

US "single crochet" and UK "double crochet" are one stitch. US "double
crochet" is UK "treble". So the word "dc" means one thing in a US pattern and
a taller, quite different thing in a British one — which is why a pattern that
does not say which it uses can quietly ruin a piece.

The app stores stitches as operations, never as words: SC is a stitch, not a
name. This table is the only place that turns an operation into a word, and it
does it twice — once for each side of the Atlantic. Switching between them
changes nothing about the piece: the stitches, the counts, the yarn and the
size are identical. Only the words move.

Source: the Craft Yarn Council's US terms and the standard UK equivalents as
published in conversion charts.
"""
from __future__ import annotations

# operation -> (US abbreviation, US name, UK abbreviation, UK name)
TERMS: dict[str, tuple[str, str, str, str]] = {
    "CH":       ("ch", "Chain", "ch", "Chain"),
    "SLST":     ("sl st", "Slip stitch", "ss", "Slip stitch"),
    "SC":       ("sc", "Single crochet", "dc", "Double crochet"),
    "HDC":      ("hdc", "Half double crochet", "htr", "Half treble crochet"),
    "DC":       ("dc", "Double crochet", "tr", "Treble crochet"),
    "TR":       ("tr", "Treble crochet", "dtr", "Double treble crochet"),
    "DTR":      ("dtr", "Double treble crochet", "trtr", "Triple treble crochet"),
    "SC_INC":   ("inc", "Increase — 2 sc in one stitch",
                 "inc", "Increase — 2 dc in one stitch"),
    "HDC_INC":  ("hdc inc", "Increase — 2 hdc in one stitch",
                 "htr inc", "Increase — 2 htr in one stitch"),
    "DC_INC":   ("dc inc", "Increase — 2 dc in one stitch",
                 "tr inc", "Increase — 2 tr in one stitch"),
    "SC2TOG":   ("dec", "Decrease — 2 sc together", "dec", "Decrease — 2 dc together"),
    "SC3TOG":   ("sc3tog", "Decrease — 3 sc together", "dc3tog", "Decrease — 3 dc together"),
    "HDC2TOG":  ("hdc2tog", "Decrease — 2 hdc together", "htr2tog", "Decrease — 2 htr together"),
    "DC2TOG":   ("dc2tog", "Decrease — 2 dc together", "tr2tog", "Decrease — 2 tr together"),
    "DC3TOG":   ("dc3tog", "Decrease — 3 dc together", "tr3tog", "Decrease — 3 tr together"),
    "SC_BLO":   ("sc blo", "Single crochet, back loop only",
                 "dc blo", "Double crochet, back loop only"),
    "SC_FLO":   ("sc flo", "Single crochet, front loop only",
                 "dc flo", "Double crochet, front loop only"),
    "HDC_BLO":  ("hdc blo", "Half double crochet, back loop only",
                 "htr blo", "Half treble crochet, back loop only"),
    "DC_BLO":   ("dc blo", "Double crochet, back loop only",
                 "tr blo", "Treble crochet, back loop only"),
    "FPDC":     ("fpdc", "Front post double crochet", "fptr", "Front post treble crochet"),
    "BPDC":     ("bpdc", "Back post double crochet", "bptr", "Back post treble crochet"),
    "PUFF3":    ("puff", "Puff stitch", "puff", "Puff stitch"),
    "POPCORN5": ("popcorn", "Popcorn stitch", "popcorn", "Popcorn stitch"),
}

# Terms that are the same either side, so the switch never touches them.
SHARED = {
    "inc": "increase — work 2 stitches into the same stitch",
    "dec": "decrease — work 2 stitches together as one",
    "blo": "back loop only", "flo": "front loop only",
    "rs": "right side — the side that will show", "ws": "wrong side — the inside",
    "rep": "repeat what is in the brackets", "rnd": "round",
    "st / sts": "stitch / stitches", "tog": "together",
    "yo": "yarn over — wrap the yarn round the hook",
    "( ) and [ ]": "repeat what is inside, or the stitch count at the end of a round",
}

DIALECTS = ("us", "uk")
DEFAULT = "us"
# The one that costs people a whole piece when they get it wrong.
HEADLINE = ("US single crochet (sc) is exactly the same stitch as "
            "UK double crochet (dc) — one name, two countries.")


def normalise(dialect: str | None) -> str:
    value = str(dialect or DEFAULT).strip().lower()
    return value if value in DIALECTS else DEFAULT


def abbr(op: str, dialect: str = DEFAULT) -> str:
    row = TERMS.get(op)
    if not row:
        return op.lower()
    return row[0] if normalise(dialect) == "us" else row[2]


def name(op: str, dialect: str = DEFAULT) -> str:
    row = TERMS.get(op)
    if not row:
        return op
    return row[1] if normalise(dialect) == "us" else row[3]


def words(dialect: str = DEFAULT) -> dict[str, str]:
    """operation -> abbreviation, the map a written pattern is printed from."""
    return {op: abbr(op, dialect) for op in TERMS}


def differs(op: str) -> bool:
    """Whether this stitch is actually called something else on the other side."""
    row = TERMS.get(op)
    return bool(row and row[0] != row[2])


def table() -> list[dict]:
    """Both names for every stitch, for showing the conversion itself."""
    return [{"operation_id": op, "us_abbr": row[0], "us_name": row[1],
             "uk_abbr": row[2], "uk_name": row[3], "differs": row[0] != row[2]}
            for op, row in TERMS.items()]
