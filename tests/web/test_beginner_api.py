"""The path for someone who has never used the app: what, how big, done."""
from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)


def plan(project, answers=None, **extra):
    return c.post("/api/beginner/plan",
                  json={"project": project, "yarn_id": "YARNSMITHS_COTTONARAN",
                        "answers": answers or {}, **extra})


def test_the_projects_are_named_the_way_a_person_would_name_them():
    projects = c.get("/api/beginner/projects").json()["projects"]
    ids = {p["id"] for p in projects}
    assert {"ball", "coaster", "hat", "scarf", "blanket"} <= ids
    for project in projects:
        assert project["name"].startswith("A ")
        assert project["about"] and project["asks"]
        for ask in project["asks"]:
            assert ask["label"] and ask["unit"] and ask["min"] < ask["max"]


def test_two_answers_produce_a_whole_piece():
    d = plan("hat", {"head_cm": 56, "height_cm": 20}).json()
    assert d["result"]["calculation"]["recommended_length_m"] > 0
    assert d["gauge"]["hook_mm"] > 0
    assert d["written"][0].startswith("R1:")
    assert len(d["written"]) > 10
    assert d["result"]["worklog_entry_id"]                 # and it is in their log
    assert any("Craft Yarn Council" in n for n in d["notes"])
    assert any("swatch" in n for n in d["notes"])          # honest about the estimate


def test_a_flat_circle_is_not_given_a_height():
    """A ten centimetre coaster is not four centimetres thick, whatever
    multiplying rounds by row height says."""
    d = plan("coaster", {"diameter_cm": 20}).json()
    size = d["result"]["finished_size"]
    assert size["lies_flat"] is True
    assert "across" in size["summary"] and "×" not in size["summary"]
    assert size["height_cm"] < size["height_if_stacked_cm"] / 3


def test_a_stuffed_piece_gets_a_smaller_hook_than_a_flat_one():
    ball = plan("ball", {"diameter_cm": 8}).json()
    coaster = plan("coaster", {"diameter_cm": 8}).json()
    assert ball["gauge"]["hook_mm"] < coaster["gauge"]["hook_mm"]
    assert ball["gauge"]["gauge_stitches_per_10cm"] > coaster["gauge"]["gauge_stitches_per_10cm"]


def test_what_the_person_measured_beats_what_was_suggested():
    mine = plan("coaster", {"diameter_cm": 10},
                gauge_stitches_per_10cm=24, gauge_rows_per_10cm=26, hook_mm=2.5).json()
    assert mine["gauge"]["gauge_stitches_per_10cm"] == 24
    assert mine["gauge"]["hook_mm"] == 2.5
    assert "gauge you measured" in mine["gauge"]["note"]


def test_a_scarf_reads_in_rows_and_a_ball_in_rounds():
    scarf = plan("scarf", {"width_cm": 20, "length_cm": 150}).json()
    assert scarf["written"][0].startswith("Row 1:")
    assert scarf["result"]["construction"]["id"] == "flat_rows"
    ball = plan("ball", {"diameter_cm": 8}).json()
    assert ball["written"][0].startswith("R1:")
    assert ball["result"]["construction"]["id"] == "round_closed"


def test_nonsense_is_refused_in_words_a_person_can_act_on():
    too_big = plan("hat", {"head_cm": 500})
    assert too_big.status_code == 422
    assert "between 35 and 70" in too_big.json()["detail"]
    assert plan("spaceship").status_code == 422
    assert c.post("/api/beginner/plan", json={"project": "hat"}).status_code == 422
