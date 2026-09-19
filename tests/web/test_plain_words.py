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


def test_one_stitch_two_names():
    """US single crochet and UK double crochet are the same stitch. The app
    stores the stitch and prints whichever name is switched on."""
    prog = {"initial_stitches": 6, "rounds": [{"operations": {"SC": 6}}]}
    us = c.post("/api/crochet/amigurumi/written", json={**prog, "terms": "us"}).json()
    uk = c.post("/api/crochet/amigurumi/written", json={**prog, "terms": "uk"}).json()
    assert us["lines"][0] == "R1: 6 sc in magic ring (6)"
    assert uk["lines"][0] == "R1: 6 dc in magic ring (6)"
    assert us["stitch_counts"] == uk["stitch_counts"]        # nothing about the piece moves
    tall = {"initial_stitches": 12, "rounds": [{"operations": {"DC": 12}}]}
    # a piece of trebles reads in trebles, in whichever country's words
    assert "dc in each st" in c.post("/api/crochet/amigurumi/written",
                                     json={**tall, "terms": "us"}).json()["lines"][1]
    assert "tr in each st" in c.post("/api/crochet/amigurumi/written",
                                     json={**tall, "terms": "uk"}).json()["lines"][1]
    # and a piece worked in trebles starts with trebles, not with single crochet
    assert c.post("/api/crochet/amigurumi/written",
                  json={**tall, "terms": "us"}).json()["lines"][0].startswith("R1: 12 dc")


def test_switching_terms_never_changes_the_piece():
    program = {"initial_stitches": 6,
               "rounds": [{"operations": {"SC_INC": 6}}, {"operations": {"SC": 6, "SC_INC": 6}}]}
    figures = []
    for dialect in ("us", "uk"):
        r = c.post("/api/complex-consumption/calculate",
                   json={**BASE, "construction": "round_closed", "program": program,
                         "terms": dialect}).json()
        figures.append((r["calculation"]["recommended_length_m"],
                        r["finished_size"]["summary"], r["program_analysis"]["operation_counts"]))
    assert figures[0] == figures[1], "terminology is a label, not a stitch"


def test_the_conversion_table_is_available_and_honest():
    body = c.get("/api/terms").json()
    rows = {r["operation_id"]: r for r in body["stitches"]}
    assert rows["SC"]["us_abbr"] == "sc" and rows["SC"]["uk_abbr"] == "dc"
    assert rows["DC"]["us_abbr"] == "dc" and rows["DC"]["uk_abbr"] == "tr"
    assert rows["CH"]["differs"] is False                     # some are the same either side
    assert rows["SC"]["differs"] is True
    assert "US single crochet (sc)" in body["headline"]
    assert body["shared"]["yo"].startswith("yarn over")


def test_the_stitch_reference_shows_the_other_name_too():
    uk = {s["operation_id"]: s for s in
          c.get("/api/stitches", params={"terms": "uk"}).json()["stitches"]}
    assert uk["SC"]["abbreviation"] == "dc" and uk["SC"]["name"] == "Double crochet"
    assert uk["SC"]["other_abbr"] == "sc"                     # and says what it is elsewhere
    assert uk["CH"]["other_abbr"] is None                     # nothing to say when it is the same


def test_the_switch_is_in_the_header():
    html = c.get("/").text
    assert 'id="termsUS"' in html and 'id="termsUK"' in html
    assert "aria-label=\"Crochet terms\"" in html
    assert "function setTerms(dialect" in html
    assert "ye_terms" in html                                  # remembered between visits
