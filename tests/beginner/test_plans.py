"""A first piece: two answers in, a real piece out."""
import pytest

from src.beginner.plans import CYC_CROCHET, PROJECTS, build, suggest_gauge


def test_the_suggested_hook_and_gauge_come_from_the_published_ranges():
    aran = suggest_gauge(4)
    low, high = CYC_CROCHET[4]["gauge"]
    assert low <= aran["gauge_stitches_per_10cm"] <= high
    hook_low, hook_high = CYC_CROCHET[4]["hook_mm"]
    assert hook_low <= aran["hook_mm"] <= hook_high
    assert "Craft Yarn Council" in aran["note"] and "swatch" in aran["note"]


def test_a_stuffed_piece_is_worked_tighter_and_says_why():
    soft, firm = suggest_gauge(4), suggest_gauge(4, firm=True)
    assert firm["gauge_stitches_per_10cm"] > soft["gauge_stitches_per_10cm"]
    assert firm["hook_mm"] < soft["hook_mm"]
    assert "stuffing cannot show through" in firm["note"]


def test_an_unknown_yarn_weight_admits_it_is_guessing():
    unknown = suggest_gauge(None)
    assert unknown["known"] is False
    assert "default" in unknown["note"] and "swatch" in unknown["note"]


@pytest.mark.parametrize("project_id", list(PROJECTS))
def test_every_project_builds_a_piece_that_holds_together(project_id):
    from src.crochet.amigurumi import analyse_rounds
    from src.web.app import service
    spec = PROJECTS[project_id]
    gauge = suggest_gauge(4, firm=spec["firm"])
    plan = build(project_id, {}, gauge)
    assert plan["construction"] in ("round_closed", "flat_rows")
    assert plan["program"]["rounds"], "a project with no rounds is not a project"
    assert plan["notes"], "every project says something worth knowing"
    analysed = analyse_rounds(plan["program"], service.operations)
    assert analysed["valid"], analysed.get("issues")


def test_a_size_nobody_could_mean_is_refused_in_words():
    with pytest.raises(ValueError) as caught:
        build("hat", {"head_cm": 500}, suggest_gauge(4))
    assert "between 35 and 70" in str(caught.value)
    with pytest.raises(ValueError):
        build("ball", {"diameter_cm": "biggish"}, suggest_gauge(4))
    with pytest.raises(KeyError):
        build("spaceship", {}, suggest_gauge(4))


def test_a_hat_is_worked_smaller_than_the_head():
    from src.crochet.amigurumi import analyse_rounds
    from src.construction.types import finished_size
    from src.web.app import service
    gauge = suggest_gauge(4)
    plan = build("hat", {"head_cm": 56, "height_cm": 20}, gauge)
    analysed = analyse_rounds(plan["program"], service.operations)
    size = finished_size("round_closed", analysed["trace"],
                         gauge_stitches_per_10cm=gauge["gauge_stitches_per_10cm"],
                         gauge_rows_per_10cm=gauge["gauge_rows_per_10cm"],
                         initial_stitches=plan["program"]["initial_stitches"])
    assert 50 < size["circumference_cm"] < 56, "a hat that fits a 56 cm head grips it"
    assert any("smaller than the head" in n for n in plan["notes"])
