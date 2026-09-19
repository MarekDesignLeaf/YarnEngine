"""The three ways a piece becomes more than one, over the wire."""
from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)


def plan(**body):
    return c.post("/api/branching/plan", json=body)


def test_the_ways_are_offered_with_what_each_is_for():
    modes = c.get("/api/branching").json()["modes"]
    by_id = {m["id"]: m for m in modes}
    assert {"sewn", "joined", "split"} == set(by_id)
    # Sewn comes first: it is what tentacles and ears actually are.
    assert modes[0]["id"] == "sewn"
    assert any("tentacles" in e for e in by_id["sewn"]["examples"])
    assert any("legs" in e for e in by_id["joined"]["examples"])


def test_two_legs_into_a_body_over_the_wire():
    d = plan(mode="joined", parts=[12, 12], chains_between=2).json()
    assert d["valid"] and d["stitches"] == 28
    assert d["operations"] == {"SC": 24, "CH": 4}


def test_a_body_into_two_legs_over_the_wire():
    d = plan(mode="split", stitches=44, pieces=2, chains_between=2).json()
    assert d["valid"] and d["branches"] == [24, 24]


def test_something_the_stitches_do_not_allow_comes_back_as_a_sentence():
    """Not a 500 and not a code: the maker asked for something impossible and
    needs to be told which bit."""
    d = plan(mode="split", stitches=6, pieces=3).json()
    assert d["valid"] is False
    assert d["issues"] and "cannot be worked in the round" in d["issues"][0]


def test_an_unknown_way_of_joining_is_refused_in_words():
    r = plan(mode="glued")
    assert r.status_code == 422
    assert "not a way of joining" in r.json()["detail"]["message"]


def test_branched_is_now_something_a_crocheter_can_pick():
    crochet = c.get("/api/constructions", params={"craft": "crochet"}).json()["constructions"]
    branched = next(row for row in crochet if row["id"] == "branched")
    assert "legs" in branched["about"] or "legs" in " ".join(branched["examples"])
    assert any("sewn on" in n for n in branched["notes"])
