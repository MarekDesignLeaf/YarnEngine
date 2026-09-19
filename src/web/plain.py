"""Saying what went wrong in the words a crocheter uses.

A person who has crocheted for thirty years knows exactly what has happened
when a round does not use up the stitches from the round below. What they do
not know, and should never have to, is what

    {"code": "ROUND_INPUT_MISMATCH", "expected": 8, "consumed": 6}

means. That is the inside of the engine on the screen. Every issue the engine
raises is turned into a sentence here: what happened, in stitches, and what to
do about it.

The codes stay in the payload for anything that needs them; the sentence is
what a person reads.
"""
from __future__ import annotations


def _round(issue: dict, word: str) -> str:
    number = issue.get("round")
    return f"{word.capitalize()} {number}" if number else f"One {word}"


def explain(issue: dict, row_word: str = "round") -> str:
    """One issue, as a sentence."""
    if not isinstance(issue, dict):
        return str(issue)
    if issue.get("message"):
        return str(issue["message"])
    code = str(issue.get("code") or "")
    where = _round(issue, row_word)

    if code == "ROUND_INPUT_MISMATCH":
        expected = issue.get("expected")
        consumed = issue.get("consumed")
        if consumed is None or expected is None:
            return f"{where} does not use up the stitches from the {row_word} before it."
        if consumed < expected:
            short = expected - consumed
            return (f"{where} only works {consumed} of the {expected} stitches there are — "
                    f"{short} would be left unworked. Add {short} more, or take "
                    f"{short} off the {row_word} before.")
        extra = consumed - expected
        return (f"{where} tries to work {consumed} stitches but there are only {expected}. "
                f"Take {extra} off this {row_word}, or add {extra} to the one before.")
    if code in ("INITIAL_STITCHES_INVALID", "INITIAL_STITCHES_REQUIRED"):
        return "Say how many stitches the piece starts with."
    if code == "UNKNOWN_CROCHET_OPERATION":
        return (f"{where} uses a stitch this app does not know"
                + (f" ({issue['operation']})." if issue.get("operation") else "."))
    if code == "NEGATIVE_COUNT":
        return f"{where} has a stitch worked a negative number of times."
    if code == "TARGET_OPERATION_UNAVAILABLE":
        return f"{where} uses a stitch that is not in this app's stitch list."
    if code == "EMPTY_ROW":
        return f"{where} has no stitches in it."
    if code:
        # An unexpected code still reads as a sentence rather than as JSON.
        pretty = code.replace("_", " ").lower()
        return f"{where}: {pretty}."
    return "Something in these rounds does not add up."


def explain_all(issues, row_word: str = "round") -> list[str]:
    seen, out = set(), []
    for issue in issues or []:
        sentence = explain(issue, row_word)
        if sentence not in seen:
            seen.add(sentence)
            out.append(sentence)
    return out


def problem(issues, row_word: str = "round") -> dict:
    """The body of a refusal: sentences first, codes kept for anything technical."""
    sentences = explain_all(issues, row_word)
    return {"message": " ".join(sentences) if sentences else "These rounds do not add up.",
            "problems": sentences,
            "program_issues": list(issues or [])}
