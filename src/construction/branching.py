"""Getting from one round to several — legs, arms, tentacles — and back again.

A piece worked in the round is one circle, and most toys are not. Somewhere
there has to be a moment where one circle becomes two, or two become one, and
the app has been silent about it: the engine only ever knew a single chain of
rounds, so a pair of legs was two unrelated pieces and the body they turn into
was a third, with nothing saying they were the same toy.

There are only three ways a crocheter actually does this, and the difference
between them matters more than the arithmetic:

  sewn      The parts are separate pieces, finished off, and stitched on at
            the end. This is how ears, arms, tails and an octopus's tentacles
            are made, and it is nearly always the right answer -- a tentacle
            is not split off anything.
  joined    The parts are made separately and then worked into one round:
            around leg one, straight on around leg two, and from there it is a
            body. The classic way to start a two-legged toy.
  split     One round is divided and each share carries on as its own tube.
            Trousers worked downwards, a mitten thumb, a body that becomes
            two legs.

The arithmetic is small but it is the part people get wrong, because the
chains that bridge the gap are stitches too: they go into the new round's
count, and they eat yarn. Everything here returns the numbers *and* the line a
person would read in a pattern, because a stitch count with no sentence round
it is what made this app unreadable in the first place.

Nothing here invents a shape. It says how many stitches each piece has and
what it costs; how tall the result is belongs to the pieces.
"""
from __future__ import annotations

# Below this many stitches a tube is not really workable in the round: the
# fabric fights the hook and the hole never closes. Real patterns bottom out
# around six.
COMFORTABLE_MINIMUM = 6
AWKWARD_MINIMUM = 4

MODES = {
    "sewn": {
        "id": "sewn", "name": "Made separately and sewn on",
        "about": ("Each part is its own finished piece, stuffed if it needs to be, and stitched "
                  "on at the end. Ears, arms, tails, tentacles, a nose."),
        "examples": ("an octopus's tentacles", "a bear's arms", "ears", "a tail"),
        "continuous": False,
    },
    "joined": {
        "id": "joined", "name": "Made separately, then joined into one round",
        "about": ("The parts are worked first and left with their stitches live. One round then "
                  "goes around the first, straight on around the next, and carries on as one "
                  "piece."),
        "examples": ("two legs becoming a body", "two sleeves and a body meeting at a yoke"),
        "continuous": True,
    },
    "split": {
        "id": "split", "name": "Split off this piece",
        "about": ("The round is divided: each share is bridged with a few chains to close it into "
                  "its own ring, and then each one carries on as its own tube."),
        "examples": ("a body that becomes two legs", "trousers worked downwards",
                     "a mitten thumb set aside"),
        "continuous": True,
    },
}


def _plural(n: int, word: str) -> str:
    if n == 1:
        return f"{n} {word}"
    # "stitchs" is the kind of small wrongness that makes a person stop
    # trusting everything else on the page.
    return f"{n} {word}es" if word.endswith(("ch", "sh", "s", "x")) else f"{n} {word}s"


def join(parts: list[int], chains_between: int = 0, skip_each_side: int = 0,
         stitch: str = "SC") -> dict:
    """Several live pieces worked into one round.

    Going around the outside of the pieces crosses from one to the next once
    per piece -- two legs meet in two places, front and back -- so chains added
    at the crossings count once per piece, not once in total. That is the sum
    people get wrong, and it is why a body comes out two stitches short.
    """
    parts = [int(p) for p in (parts or [])]
    issues: list[str] = []
    if len(parts) < 2:
        return {"valid": False, "issues": ["Joining needs at least two pieces."]}
    if any(p < 1 for p in parts):
        return {"valid": False, "issues": ["Every piece being joined needs at least one stitch."]}
    chains = max(0, int(chains_between))
    skip = max(0, int(skip_each_side))
    crossings = len(parts)                      # the pieces close into a ring
    lost = crossings * 2 * skip
    total = sum(parts) + crossings * chains - lost
    if total < AWKWARD_MINIMUM:
        issues.append("That leaves too few stitches to work in the round.")
    for i, p in enumerate(parts, 1):
        if p - 2 * skip < 1:
            issues.append(f"Piece {i} has only {_plural(p, 'stitch')}, "
                          f"so skipping {skip} at each side would use them all up.")
    ops: dict[str, int] = {stitch: sum(parts) - lost}
    if chains:
        ops["CH"] = crossings * chains
    # The line a person reads. Named pieces, in order, with the chains where
    # they actually fall.
    bits = []
    for i, p in enumerate(parts, 1):
        worked = p - 2 * skip
        bits.append(f"{_plural(worked, 'st')} of piece {i}")
        if chains:
            bits.append(f"ch {chains}")
    line = f"work in {', '.join(bits)} ({total})"
    how = (f"Hold the pieces together in the order they go round. Work around the first, "
           f"carry straight on around the next" +
           (f", chaining {chains} across each gap" if chains else "") +
           (f", skipping {_plural(skip, 'stitch')} at each side of every gap" if skip else "") +
           f". From here it is one piece of {_plural(total, 'stitch')}.")
    out = {"valid": not issues, "mode": "joined", "parts": parts, "chains_between": chains,
           "skip_each_side": skip, "crossings": crossings, "stitches": total,
           "operations": {k: v for k, v in ops.items() if v > 0},
           "line": line, "how": how, "issues": issues, "notes": []}
    if not chains:
        out["notes"].append(
            "With no chains between them the pieces sit tight against each other, which leaves a "
            "small gap to close by hand at the end. Two or three chains at each gap fills it in "
            "as you go.")
    if total < COMFORTABLE_MINIMUM and not issues:
        out["notes"].append(f"{_plural(total, 'stitch')} is very tight to work in the round.")
    return out


def split(stitches: int, shares: list[int], chains_between: int = 0,
          stitch: str = "SC") -> dict:
    """One round divided, each share closing into its own tube.

    Each share is bridged with the same few chains, so every branch ends up
    with its share plus those chains -- which is why splitting 44 stitches in
    half with two chains gives two tubes of 24 and not of 22.
    """
    stitches = int(stitches or 0)
    shares = [int(s) for s in (shares or [])]
    issues: list[str] = []
    if stitches < 1:
        return {"valid": False, "issues": ["Say how many stitches the round has before it splits."]}
    if len(shares) < 2:
        return {"valid": False, "issues": ["Splitting means at least two pieces."]}
    if any(s < 1 for s in shares):
        return {"valid": False, "issues": ["Every piece needs at least one stitch of its own."]}
    chains = max(0, int(chains_between))
    if sum(shares) != stitches:
        issues.append(f"The pieces add up to {sum(shares)}, but the round has "
                      f"{_plural(stitches, 'stitch')} to divide. Every stitch has to go somewhere.")
    branches = [s + chains for s in shares]
    for i, b in enumerate(branches, 1):
        if b < AWKWARD_MINIMUM:
            issues.append(f"Piece {i} would have only {_plural(b, 'stitch')}, which cannot be "
                          f"worked in the round.")
    ops: dict[str, int] = {stitch: stitches}
    if chains:
        ops["CH"] = chains * len(shares)
    lines = []
    for i, (share, total) in enumerate(zip(shares, branches), 1):
        lines.append(f"piece {i}: {_plural(share, 'st')}" +
                     (f" + ch {chains} across the gap" if chains else "") + f" ({total})")
    how = (f"Work {_plural(shares[0], 'stitch')}" +
           (f", chain {chains} across to where you started" if chains else
            ", then slip stitch to where you started") +
           f" — that closes the first piece into a ring of {_plural(branches[0], 'stitch')}. "
           f"Leave the rest for now, work this piece to its full length, then come back and do "
           f"the same with each of the others.")
    out = {"valid": not issues, "mode": "split", "stitches": stitches, "shares": shares,
           "chains_between": chains, "branches": branches,
           "operations": {k: v for k, v in ops.items() if v > 0},
           "lines": lines, "how": how, "issues": issues, "notes": []}
    small = [i for i, b in enumerate(branches, 1) if AWKWARD_MINIMUM <= b < COMFORTABLE_MINIMUM]
    if small:
        out["notes"].append(
            f"Piece{'s' if len(small) > 1 else ''} {', '.join(map(str, small))} "
            f"{'are' if len(small) > 1 else 'is'} under {COMFORTABLE_MINIMUM} stitches, which is "
            f"fiddly in the round — most people make anything that thin as a separate piece and "
            f"sew it on.")
    if not chains and out["valid"]:
        out["notes"].append(
            "With no chains the two pieces meet at a point, which pulls. Two or three chains "
            "across each gap is what stops a crotch or an underarm from puckering.")
    return out


def even_shares(stitches: int, pieces: int) -> list[int]:
    """The plainest division: as equal as the stitch count allows.

    A round rarely divides exactly, so the remainder is spread one stitch at a
    time rather than dumped on the last piece -- the difference between legs
    that match and one that is three stitches fatter.
    """
    stitches, pieces = int(stitches or 0), max(1, int(pieces or 1))
    base, extra = divmod(max(0, stitches), pieces)
    return [base + (1 if i < extra else 0) for i in range(pieces)]


def sewn(parts: list[int]) -> dict:
    """Parts that are simply separate pieces. No arithmetic — that is the point."""
    parts = [int(p) for p in (parts or [])]
    return {
        "valid": bool(parts), "mode": "sewn", "parts": parts, "stitches": None,
        "operations": {},
        "how": ("Each of these is its own piece, worked and finished on its own, then stitched on "
                "where it goes. Nothing has to line up with anything: the stitch counts are "
                "whatever each piece needs."),
        "issues": [] if parts else ["Say how many pieces there are."],
        "notes": ["Pinning the pieces on and standing back before sewing is worth more than any "
                  "number here — where they go decides what the toy looks like."],
    }


def plan(payload: dict) -> dict:
    """Whichever of the three a maker picked, answered in the same shape."""
    mode = str(payload.get("mode") or "sewn").lower()
    stitch = str(payload.get("stitch") or "SC").upper()
    if mode not in MODES:
        return {"valid": False, "issues": [f"“{mode}” is not a way of joining pieces."],
                "modes": list(MODES)}
    if mode == "sewn":
        out = sewn(payload.get("parts") or [])
    elif mode == "joined":
        out = join(payload.get("parts") or [], int(payload.get("chains_between") or 0),
                   int(payload.get("skip_each_side") or 0), stitch)
    else:
        shares = payload.get("shares")
        if not shares:
            shares = even_shares(int(payload.get("stitches") or 0),
                                 int(payload.get("pieces") or 2))
        out = split(int(payload.get("stitches") or 0), shares,
                    int(payload.get("chains_between") or 0), stitch)
    out.setdefault("notes", [])
    out["name"] = MODES[mode]["name"]
    out["about"] = MODES[mode]["about"]
    return out


def listing() -> list[dict]:
    return [dict(m, minimum_stitches=COMFORTABLE_MINIMUM) for m in MODES.values()]
