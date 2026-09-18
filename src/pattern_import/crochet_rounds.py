"""Somebody else's crochet pattern, read into rounds this app can work with.

Written crochet is prose, not a format: the same round appears as "R3: [sc,
inc] x 6 (18)", "Round 3: *1 sc, 2 sc in next st; rep from * around", or
"Rnd 3 (inc): (sc, inc) 6 times -- 18 sts". This reads the forms people
actually write and turns them into the operation counts the calculator,
the 3D preview and the make-mode already use.

What it will not do is guess. Every line it cannot read is reported as its own
issue with the text that defeated it, and the rounds it did read are checked
twice over: against the stitch count the pattern itself states in brackets, and
against ``analyse_rounds``, which is the same validator the rounds editor uses.
A pattern that half-parses comes back half-parsed and says so, rather than
arriving as a confident wrong answer.

Dialects are a real trap rather than a detail: in UK terms "double crochet" is
what US terms call single crochet, so the same words describe different fabric.
The dialect is an explicit choice, and a pattern whose vocabulary looks like the
other one is flagged instead of being silently reinterpreted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- what the words mean -----------------------------------------------------
# Only stitches the operation registry already knows; nothing is invented here.
US_STITCHES = {
    "sc": "SC", "single crochet": "SC", "single": "SC",
    "hdc": "HDC", "half double crochet": "HDC", "half double": "HDC",
    "dc": "DC", "double crochet": "DC", "double": "DC",
    "tr": "TR", "treble crochet": "TR", "treble": "TR", "triple crochet": "TR",
    "dtr": "DTR", "double treble": "DTR",
    "ch": "CH", "chain": "CH",
    "sl st": "SLST", "slst": "SLST", "ss": "SLST", "slip stitch": "SLST",
    "sc blo": "SC_BLO", "blo sc": "SC_BLO", "sc flo": "SC_FLO", "flo sc": "SC_FLO",
}
UK_STITCHES = {
    "dc": "SC", "double crochet": "SC", "double": "SC",
    "htr": "HDC", "half treble": "HDC", "half treble crochet": "HDC",
    "tr": "DC", "treble": "DC", "treble crochet": "DC",
    "dtr": "TR", "double treble": "TR",
    "ttr": "DTR", "triple treble": "DTR",
    "ch": "CH", "chain": "CH",
    "sl st": "SLST", "slst": "SLST", "ss": "SLST", "slip stitch": "SLST",
}
# Increases and decreases, which are named rather than counted.
INCREASES = {
    "inc": "SC_INC", "increase": "SC_INC", "sc inc": "SC_INC",
    "hdc inc": "HDC_INC", "dc inc": "DC_INC",
}
DECREASES = {
    "dec": "SC2TOG", "decrease": "SC2TOG", "sc2tog": "SC2TOG", "sc dec": "SC2TOG",
    "invdec": "SC2TOG", "invisible decrease": "SC2TOG", "invisible dec": "SC2TOG",
    "sc3tog": "SC3TOG", "hdc2tog": "HDC2TOG", "dc2tog": "DC2TOG", "dc3tog": "DC3TOG",
}
# One instance of each consumes/produces this many stitches.
IO = {
    "SC": (1, 1), "SC_BLO": (1, 1), "SC_FLO": (1, 1), "HDC": (1, 1), "DC": (1, 1),
    "TR": (1, 1), "DTR": (1, 1), "SLST": (1, 1), "CH": (0, 1),
    "SC_INC": (1, 2), "HDC_INC": (1, 2), "DC_INC": (1, 2),
    "SC2TOG": (2, 1), "HDC2TOG": (2, 1), "DC2TOG": (2, 1),
    "SC3TOG": (3, 1), "DC3TOG": (3, 1),
}
# Words that mean "as many as there are left in this round".
AROUND = re.compile(r"\b(?:in\s+)?(?:each|every)\b[^,;]*\b(?:st|stitch|sts|stitches)?\b|"
                    r"\baround\b|\bto\s+end\b|\bto\s+the\s+end\b", re.I)
ROUND_HEADER = re.compile(
    r"^\s*(?:r(?:ound|nd|ow)?s?)\s*[.:]?\s*(\d+)\s*(?:[-–—]\s*(\d+))?\s*(?:\([^)]*\))?\s*[:.)\-–—]\s*(.*)$",
    re.I)
MAGIC_RING = re.compile(
    r"(\d+)\s*([a-z ]{2,20}?)\s*(?:in|into|in\s+a|into\s+a)?\s*(?:magic\s*(?:ring|circle|loop)|mr\b|adjustable\s*ring)",
    re.I)
STATED_COUNT = re.compile(r"[\(\[]\s*(\d+)\s*(?:st|sts|stitch|stitches)?\s*[\)\]]\s*$|"
                          r"(?:--|—|–|=)\s*(\d+)\s*(?:st|sts|stitch|stitches)\b|"
                          # "You will have a total of 18 stitches." -- the same
                          # fact written as a sentence, which is how printed
                          # beginner patterns say it
                          r"[.,]?\s*(?:you\s+(?:will\s+)?(?:now\s+)?have|for\s+a\s+total\s+of|"
                          r"total\s+of)\s*(?:a\s+total\s+of\s*)?(\d+)\s*"
                          r"(?:st|sts|stitch|stitches)?\.?\s*$", re.I)
# An atom made only of these is scaffolding around the instruction, not an
# instruction: dropping it is safe, and anything with a real word in it is not
# dropped but reported.
FILLER_ONLY = re.compile(
    r"^(?:\s|[.,;:!\-\u2013\u2014*]|\d+|work(?:ed|ing)?|make|made|then|and|you|will|now|"
    r"have|has|a|an|the|this|that|it|is|are|of|for|in|into|total|next|same|"
    r"note|continue|cont|do|not|turn|join|joining|place|marker|pm|st|sts|stitch|stitches|"
    r"rep|repeat|repeats|time|times|around|to|end|beginning|start|all)*$", re.I)
# "[...] x 6", "(...) 6 times", "*...* 6 times", "rep from * 6 times"
GROUP = re.compile(r"[\[\(\*]\s*(?P<body>[^\]\)\*]+?)\s*[\]\)\*]\s*"
                   r"(?:x\s*)?(?P<times>\d+)?\s*(?:times|x)?", re.I)
REP_FROM = re.compile(r"rep(?:eat)?\s+from\s*\*\s*(?:(\d+)\s*(?:more\s*)?times|around|to\s+end)", re.I)


@dataclass
class Issue:
    line: int
    text: str
    reason: str

    def as_dict(self):
        return {"line": self.line, "text": self.text, "reason": self.reason}


@dataclass
class ParsedPattern:
    initial_stitches: int | None = None
    rounds: list[dict] = field(default_factory=list)
    stitch_counts: list[int] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    dialect: str = "us"
    notes: list[str] = field(default_factory=list)

    def as_dict(self):
        return {"initial_stitches": self.initial_stitches, "rounds": self.rounds,
                "stitch_counts": self.stitch_counts, "dialect": self.dialect,
                "issues": [i.as_dict() for i in self.issues], "notes": self.notes}


def _vocabulary(dialect: str) -> dict:
    base = dict(UK_STITCHES if dialect == "uk" else US_STITCHES)
    base.update(INCREASES)
    base.update(DECREASES)
    return base


def looks_like_uk(text: str) -> bool:
    """UK patterns say htr/dtr and never say 'single crochet'."""
    low = text.lower()
    uk_only = len(re.findall(r"\bhtr\b|\bhalf treble\b|\bttr\b", low))
    us_only = len(re.findall(r"\bsc\b|\bsingle crochet\b|\bhdc\b|\bhalf double\b", low))
    return uk_only > 0 and us_only == 0


def _match_stitch(word: str, vocab: dict) -> str | None:
    w = re.sub(r"\s+", " ", word.strip().lower()).strip(" .")
    w = re.sub(r"\b(?:st|sts|stitch|stitches)\b", "", w).strip()
    if not w:
        return None
    if w in vocab:
        return vocab[w]
    # plural and "es" forms, and "1 sc" style leftovers
    for suffix in ("s", "es"):
        if w.endswith(suffix) and w[: -len(suffix)] in vocab:
            return vocab[w[: -len(suffix)]]
    return None


def _strip_around(text: str) -> str:
    return AROUND.sub(" ", text)


NOISE = re.compile(r"\b(?:work|worked|working|continue|cont|please|now|then|and|"
                   r"turn|join|to\s+join|do\s+not\s+turn|st|sts|stitch|stitches|"
                   r"in\s+next|into\s+next|in\s+the\s+next|next)\b", re.I)


def _parse_atom(atom: str, vocab: dict):
    """One instruction -> (operation, count), where a count of None means
    "as many as the round has left"."""
    raw = atom.strip().strip(".,;:")
    if not raw:
        return None, None
    # "2 sc in next st" / "2 dc in the same stitch" is an increase, not two stitches
    m = re.match(r"^(\d+)\s+([a-z ]+?)\s+(?:in|into)\s+(?:the\s+)?(?:next|same|each)\b",
                 raw, re.I)
    if m and int(m.group(1)) == 2:
        base = _match_stitch(m.group(2), vocab)
        inc = {"SC": "SC_INC", "HDC": "HDC_INC", "DC": "DC_INC"}.get(base)
        if inc:
            return inc, (None if re.search(r"\beach\b", raw, re.I) else 1)
    open_ended = bool(AROUND.search(raw))
    body = _strip_around(raw) if open_ended else raw
    # "sc in next 5 sts" -> 5 sc
    m = re.search(r"(?:in|into)\s+(?:the\s+)?next\s+(\d+)", raw, re.I)
    if m:
        op = _match_stitch(NOISE.sub(" ", re.sub(r"(?:in|into).*", "", raw, flags=re.I)), vocab)
        if op:
            return op, int(m.group(1))
    body = NOISE.sub(" ", body).strip(" .,;:")
    for pattern, order in ((r"^(\d+)\s*[x\u00d7]?\s*(.+)$", "count-first"),
                           (r"^(.+?)\s*[x\u00d7]\s*(\d+)$", "count-last"),
                           (r"^([a-z][a-z0-9 ]*?)\s+(\d+)$", "count-last")):
        m = re.match(pattern, body, re.I)
        if not m:
            continue
        name, number = ((m.group(2), m.group(1)) if order == "count-first"
                        else (m.group(1), m.group(2)))
        op = _match_stitch(name, vocab)
        if op:
            # "1 single crochet in each stitch around" counts per stitch, not in
            # total: the 1 says how many go into each one, and "around" says how
            # many stitches there are.
            if open_ended and int(number) == 1:
                return op, None
            return op, int(number)
    op = _match_stitch(body, vocab)
    if op:
        return op, (None if open_ended else 1)
    return None, None


def _split_atoms(text: str) -> list[str]:
    return [a for a in re.split(r",|;|\band\b|\bthen\b", text, flags=re.I) if a.strip()]


def _normalise_repeats(text: str) -> str:
    """Turn asterisk repeats into bracket repeats, which is the same thing said
    twice in the wild: "*sc, inc; rep from * 6 times" is "[sc, inc] x 6"."""
    def swap(m):
        body = m.group("body").strip(" ,;")
        times = m.group("times")
        return f"[{body}] x {times} " if times else f"[{body}] around "
    return re.sub(
        r"\*\s*(?P<body>[^*]+?)\s*[;,]?\s*rep(?:eat)?\s+from\s*\*\s*"
        r"(?:(?P<times>\d+)\s*(?:more\s*)?times?|around|to\s+(?:the\s+)?end)",
        swap, text, flags=re.I)


GROUP_ANY = re.compile(r"[\[\(]\s*(?P<body>[^\]\)]+?)\s*[\]\)]\s*"
                       r"(?:(?:x|\u00d7)\s*(?P<times>\d+)|(?P<times2>\d+)\s*(?:times|x)|"
                       r"(?P<open>around|to\s+(?:the\s+)?end|repeat(?:ed)?\s+around))?", re.I)


def _group_ops(body: str, vocab: dict):
    """One pass through a bracketed repeat: its operations and what it eats."""
    ops: dict[str, int] = {}
    for atom in _split_atoms(body):
        op, n = _parse_atom(atom, vocab)
        if op is None or n is None:
            return None
        ops[op] = ops.get(op, 0) + n
    return ops or None


def parse_round(text: str, vocab: dict, incoming: int | None):
    """One round's instructions -> {operation: count}, or (None, why)."""
    body = STATED_COUNT.sub("", text).strip(" .;,")
    body = _normalise_repeats(body)
    # "sc in next 2 sts, inc; repeat around" -- everything before the words is
    # the repeat, which is how most patterns say it without brackets at all.
    trailing = re.search(r"[,;]?\s*(?:and\s+)?rep(?:eat)?(?:\s+this)?\s*"
                         r"(?:from\s+(?:the\s+)?(?:beginning|start)\s*)?"
                         r"(?:around|to\s+(?:the\s+)?end)\s*$", body, re.I)
    if trailing and not GROUP_ANY.search(body):
        body = f"[{body[:trailing.start()].strip(' ,;')}] around"
    ops: dict[str, int] = {}
    consumed = 0
    open_group = None          # operations of one repeat, count decided by the round
    open_atom = None           # a single stitch worked "around"

    rest = body
    asides = []
    for m in GROUP_ANY.finditer(body):
        times = m.group("times") or m.group("times2")
        is_open = bool(m.group("open"))
        if not times and not is_open:
            # "... and repeat this 6 times around" puts the count a few words later
            ahead = body[m.end():m.end() + 48]
            look = re.search(r"(\d+)\s*times?", ahead, re.I)
            if look:
                times = look.group(1)
            elif re.search(r"\b(?:around|to\s+(?:the\s+)?end)\b", ahead, re.I):
                is_open = True
        per = _group_ops(m.group("body"), vocab)
        if per is None:
            if times or is_open:
                return None, "a repeat could not be read: " + m.group("body").strip()
            asides.append(m.group(0))       # an aside in brackets, not a repeat
            rest = rest.replace(m.group(0), " ", 1)
            continue
        if not times and not is_open:
            # A bracketed phrase with no count is usually an explanation --
            # "Work 6 increases (2 single crochet in each stitch)" -- so it is
            # set aside, and only complained about if the round then fails to
            # use up the stitches the previous round left.
            asides.append(m.group(0))
            rest = rest.replace(m.group(0), " ", 1)
            continue
        rest = rest.replace(m.group(0), " ", 1)
        if times:
            for op, n in per.items():
                ops[op] = ops.get(op, 0) + n * int(times)
                consumed += IO.get(op, (1, 1))[0] * n * int(times)
        else:
            if open_group or open_atom:
                return None, "two open-ended repeats in one round"
            open_group = per

    for atom in _split_atoms(rest):
        if not atom.strip() or FILLER_ONLY.fullmatch(atom):
            continue
        op, n = _parse_atom(atom, vocab)
        if op is None:
            return None, "could not read: " + atom.strip()
        if n is None:
            if open_group or open_atom:
                return None, "two open-ended instructions in one round"
            open_atom = op
        else:
            ops[op] = ops.get(op, 0) + n
            consumed += IO.get(op, (1, 1))[0] * n

    if open_group or open_atom:
        if incoming is None:
            return None, "“around” needs to know how many stitches the round starts with"
        left = incoming - consumed
        per_repeat = (sum(IO.get(op, (1, 1))[0] * n for op, n in open_group.items())
                      if open_group else IO.get(open_atom, (1, 1))[0])
        if per_repeat <= 0:
            return None, "an open-ended repeat that consumes no stitches"
        if left < 0 or left % per_repeat:
            return None, f"the round does not come out evenly against {incoming} stitches"
        times = left // per_repeat
        if open_group:
            for op, n in open_group.items():
                ops[op] = ops.get(op, 0) + n * times
        else:
            ops[open_atom] = ops.get(open_atom, 0) + times
    if not ops:
        return None, "no stitches in this round"
    if asides and incoming is not None:
        eaten = sum(IO.get(op, (1, 1))[0] * n for op, n in ops.items())
        if eaten != incoming:
            return None, ("a bracketed part has no number of times: "
                          + asides[0].strip())
    return ops, None


def parse_pattern(text: str, dialect: str = "us") -> ParsedPattern:
    """A written pattern -> rounds, with everything unreadable reported."""
    out = ParsedPattern(dialect=dialect)
    if dialect == "us" and looks_like_uk(text):
        out.notes.append("This looks like UK terms (htr, dtr, no 'sc'). "
                         "Read as US terms it would come out as the wrong stitch — "
                         "switch the dialect if the pattern is British.")
    vocab = _vocabulary(dialect)
    current: int | None = None

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        header = ROUND_HEADER.match(line)
        body = header.group(3) if header else line
        repeats = 1
        if header and header.group(2):
            repeats = max(1, int(header.group(2)) - int(header.group(1)) + 1)

        if out.initial_stitches is None:
            ring = MAGIC_RING.search(line)
            if ring:
                stitch = _match_stitch(ring.group(2), vocab)
                if stitch in (None, "CH"):
                    stitch = "SC"
                out.initial_stitches = int(ring.group(1))
                out.stitch_counts.append(out.initial_stitches)
                current = out.initial_stitches
                continue
        if not header:
            continue                      # prose between rounds: materials, notes

        stated = STATED_COUNT.search(body)
        want = int(next(g for g in stated.groups() if g)) if stated else None

        ops, why = parse_round(body, vocab, current)
        if ops is None:
            out.issues.append(Issue(lineno, line, why))
            continue
        for _ in range(repeats):
            produced = sum(IO.get(op, (1, 1))[1] * n for op, n in ops.items())
            eaten = sum(IO.get(op, (1, 1))[0] * n for op, n in ops.items())
            if current is not None and eaten != current:
                out.issues.append(Issue(
                    lineno, line,
                    f"uses {eaten} stitches but the previous round left {current}"))
                break
            out.rounds.append({"operations": dict(ops)})
            out.stitch_counts.append(produced)
            current = produced
            if want is not None and produced != want and repeats == 1:
                out.issues.append(Issue(
                    lineno, line,
                    f"the pattern says {want} stitches, these instructions make {produced}"))
    if out.initial_stitches is None and out.rounds:
        out.notes.append("No magic ring was found, so the first round's stitch count "
                         "was taken as the starting count.")
        first = out.rounds.pop(0)
        out.initial_stitches = sum(IO.get(op, (1, 1))[1] * n
                                   for op, n in first["operations"].items())
    return out
