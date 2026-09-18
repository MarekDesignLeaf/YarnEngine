"""The stitch reference, built from the operation table rather than copied."""
from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)


def by_id():
    return {s["operation_id"]: s for s in c.get("/api/stitches").json()["stitches"]}


def test_every_crochet_stitch_the_app_knows_is_listed_and_nothing_else():
    stitches = by_id()
    assert {"CH", "SLST", "SC", "HDC", "DC", "TR", "SC_INC", "SC2TOG"} <= set(stitches)
    assert "K" not in stitches and "P" not in stitches      # knitting is not crochet
    assert all(s["family"].startswith("crochet") for s in stitches.values())


def test_a_stitch_carries_what_it_is_for_and_what_it_does_to_the_count():
    sc = by_id()["SC"]
    assert sc["abbreviation"] == "sc" and sc["name"] == "Single crochet"
    assert (sc["consumes"], sc["produces"]) == (1, 1)
    assert "amigurumi" in sc["use"]
    inc, dec, ch = by_id()["SC_INC"], by_id()["SC2TOG"], by_id()["CH"]
    assert (inc["consumes"], inc["produces"]) == (1, 2)
    assert (dec["consumes"], dec["produces"]) == (2, 1)
    assert (ch["consumes"], ch["produces"]) == (0, 1)


def test_the_yarn_figures_are_the_engines_own_and_hold_together():
    stitches = by_id()
    assert stitches["SC"]["relative_to_sc"] == 1.0
    assert stitches["DC"]["relative_to_sc"] == 2.0          # twice the passes
    assert stitches["HDC"]["relative_to_sc"] == 1.5
    assert stitches["DC"]["yarn_mm"] > stitches["SC"]["yarn_mm"]
    assert stitches["SC"]["measured"] is True               # anchored to real swatches
    assert stitches["PUFF3"]["measured"] is False           # and honest where it is not


def test_a_bigger_hook_costs_more_yarn_per_stitch():
    small = c.get("/api/stitches", params={"hook_mm": 2.0}).json()["stitches"]
    large = c.get("/api/stitches", params={"hook_mm": 6.0}).json()["stitches"]
    sc_small = next(s for s in small if s["operation_id"] == "SC")["yarn_mm"]
    sc_large = next(s for s in large if s["operation_id"] == "SC")["yarn_mm"]
    assert sc_large > sc_small * 1.5


def test_the_page_says_what_the_figure_is_for():
    body = c.get("/api/stitches").json()
    assert "comparing stitches" in body["note"]
    assert c.get("/api/stitches", params={"hook_mm": 0}).status_code == 422
    assert c.get("/api/stitches", params={"yarn_diameter_mm": 99}).status_code == 422


def test_the_chart_opens_where_a_person_starts():
    order = [s["operation_id"] for s in c.get("/api/stitches").json()["stitches"]]
    assert order[:7] == ["CH", "SLST", "SC", "HDC", "DC", "TR", "DTR"]
    assert order.index("SC_INC") < order.index("SC2TOG") < order.index("BPDC")
