"""The same engine costing a jumper panel, a sleeve and a bear."""
from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)
BASE = {"yarn_id": "YARNSMITHS_COTTONARAN", "hook_mm": 3.0,
        "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
        "allowance_percent": 10, "domain_policy": "warn"}


def cost(construction, program, **extra):
    return c.post("/api/complex-consumption/calculate",
                  json={**BASE, "construction": construction, "program": program, **extra})


def test_the_app_lists_the_ways_a_piece_can_be_built():
    body = c.get("/api/constructions").json()
    ids = {row["id"] for row in body["constructions"]}
    assert {"round_closed", "round_open", "flat_rows", "flat_shaped", "motif_joined"} <= ids
    assert body["default"] == "round_closed"
    assert "branched" not in {r["id"] for r in c.get("/api/constructions",
                                                     params={"craft": "crochet"}).json()["constructions"]}
    assert c.get("/api/constructions", params={"craft": "macrame"}).status_code == 422


def test_a_flat_panel_is_costed_and_measured_as_a_panel():
    r = cost("flat_rows", {"initial_stitches": 30,
                           "rounds": [{"operations": {"SC": 30}} for _ in range(20)]})
    assert r.status_code == 200
    body = r.json()
    assert body["construction"]["id"] == "flat_rows"
    assert body["construction"]["row_word"] == "row"
    assert body["finished_size"]["width_cm"] == 15.0
    assert body["finished_size"]["length_cm"] == 9.1
    assert body["calculation"]["recommended_length_m"] > 0


def test_a_sleeve_is_measured_round_and_a_head_across():
    tube = cost("round_open", {"initial_stitches": 48,
                               "rounds": [{"operations": {"SC": 48}} for _ in range(30)]}).json()
    assert "around" in tube["finished_size"]["summary"]
    head = cost("round_closed", {"initial_stitches": 6,
                                 "rounds": [{"operations": {"SC_INC": 6}},
                                            {"operations": {"SC": 6, "SC_INC": 6}}]}).json()
    assert head["finished_size"]["diameter_cm"] > 0
    assert head["construction"]["row_word"] == "round"


def test_a_shaped_panel_reports_the_width_of_every_row():
    shawl = cost("flat_shaped",
                 {"initial_stitches": 6,
                  "rounds": [{"operations": {"SC": n - 2, "SC_INC": 2}}
                             for n in range(6, 30, 2)]}).json()
    assert shawl["finished_size"]["outline"][0] < shawl["finished_size"]["outline"][-1]
    assert "cm across" in shawl["finished_size"]["summary"]


def test_a_construction_refuses_a_start_it_cannot_have():
    bad = cost("round_open", {"initial_stitches": 0,
                              "rounds": [{"operations": {"SC_INC": 6}}]})
    assert bad.status_code == 422
    codes = [i["code"] for i in bad.json()["detail"]["program_issues"]]
    assert "START_STITCHES_REQUIRED" in codes
    assert cost("wishes", {"initial_stitches": 6, "rounds": []}).status_code == 422


def test_what_already_existed_still_works_unchanged():
    """Every piece calculated before this existed was program_type amigurumi."""
    r = c.post("/api/complex-consumption/calculate", json={
        **BASE, "program_type": "amigurumi",
        "program": {"initial_stitches": 6, "rounds": [{"operations": {"SC_INC": 6}}]}})
    assert r.status_code == 200
    assert r.json()["construction"]["id"] == "round_closed"
    assert r.json()["program_type"] == "amigurumi"
