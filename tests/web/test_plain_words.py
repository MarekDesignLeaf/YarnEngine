"""What the app says to a person who crochets — and never says.

A crocheter with thirty years behind them knows exactly what has gone wrong
when a round does not use up the stitches below it. What they cannot be asked
to read is the inside of the engine.
"""
import json

from fastapi.testclient import TestClient

from src.web.app import app
from src.web.plain import explain, problem

c = TestClient(app)
BASE = {"yarn_id": "YARNSMITHS_COTTONARAN", "hook_mm": 3.0,
        "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
        "allowance_percent": 10, "domain_policy": "warn"}


def test_a_round_that_does_not_add_up_is_explained_in_stitches():
    r = c.post("/api/complex-consumption/calculate", json={
        **BASE, "program_type": "amigurumi",
        "program": {"initial_stitches": 8, "rounds": [{"operations": {"SC": 6}}]}})
    assert r.status_code == 422
    message = r.json()["detail"]["message"]
    assert "only works 6 of the 8 stitches" in message
    assert "Add 2 more" in message                      # and what to do about it
    for machinery in ("ROUND_INPUT_MISMATCH", "program_issues", "{", "code"):
        assert machinery not in message


def test_too_many_stitches_is_the_other_sentence():
    said = explain({"round": 3, "code": "ROUND_INPUT_MISMATCH", "expected": 12, "consumed": 18})
    assert "tries to work 18 stitches but there are only 12" in said
    assert "Take 6 off this round" in said


def test_the_words_follow_the_construction():
    said = explain({"round": 2, "code": "UNKNOWN_CROCHET_OPERATION", "operation": "WIGGLE"}, "row")
    assert said.startswith("Row 2")


def test_an_unknown_code_still_reads_as_a_sentence():
    """A code nobody wrote a sentence for must still not arrive as JSON."""
    said = explain({"round": 1, "code": "SOME_NEW_THING"})
    assert said == "Round 1: some new thing."
    assert "{" not in json.dumps(problem([{"code": "SOME_NEW_THING"}])["message"])


def test_a_typed_round_is_read_the_way_a_pattern_writes_it():
    d = c.post("/api/crochet/round/read",
               json={"text": "[2 sc, inc] x 6", "incoming": 18}).json()
    assert d["operations"] == {"SC": 12, "SC_INC": 6}
    assert d["output_stitches"] == 24
    assert d["written"] == "[2 sc, inc] x 6 (24)"
    # longhand comes back tidied into the way a pattern would print it
    longhand = c.post("/api/crochet/round/read",
                      json={"text": "sc, sc, inc, " * 5 + "sc, sc, inc", "incoming": 18}).json()
    assert longhand["operations"] == {"SC": 12, "SC_INC": 6}
    # a round number at the front is not part of the stitches
    assert c.post("/api/crochet/round/read",
                  json={"text": "R7: 6 inc", "incoming": 6}).json()["output_stitches"] == 12


def test_a_typed_round_that_cannot_work_says_why_in_plain_words():
    short = c.post("/api/crochet/round/read",
                   json={"text": "sc 5", "incoming": 18, "round": 4})
    assert short.status_code == 422
    assert "Round 4 only works 5 of the 18 stitches" in short.json()["detail"]["message"]

    unknown = c.post("/api/crochet/round/read", json={"text": "wiggle around", "incoming": 12})
    assert unknown.status_code == 422
    detail = unknown.json()["detail"]
    assert "“wiggle around” is not something it can read" in detail
    assert "[2 sc, inc] x 6" in detail                   # and an example of what does work
    assert c.post("/api/crochet/round/read", json={"text": "  "}).status_code == 422


def test_the_interface_uses_crochet_words_not_engine_words():
    html = c.get("/").text
    assert "Stitches used" in html and "<h3>Operations used</h3>" not in html
    assert ">Finished size<" in html
    assert "Uncalibrated estimate" not in html
    assert "function readableError(" in html            # no JSON ever reaches the screen
    assert "JSON.stringify(d.detail)" not in html
    assert "In the round, from a magic ring" in c.get("/api/constructions").text
