"""Starting shapes: a ball has to come out a ball.

The rounds editor used to draw its own starting shapes in the browser, by
adding a fixed number of stitches every round and then working straight. That
makes a drum whatever the option is called, and once the 3D preview was honest
about heights it was plain to see. These tests hold the shapes to their names.
"""
import math

from fastapi.testclient import TestClient

from src.construction.types import finished_size
from src.web.app import app

c = TestClient(app)
GAUGE = {"gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22}


def make(archetype, width_cm, height_cm=None, **extra):
    body = {"archetype": archetype, "width_cm": width_cm, **GAUGE, **extra}
    if height_cm is not None:
        body["height_cm"] = height_cm
    return c.post("/api/shapes/rounds", json=body)


def measured(payload):
    """What the piece those rounds describe actually measures."""
    trace = []
    prev = payload["initial_stitches"]
    for count in payload["stitch_counts"]:
        trace.append({"output_stitches": count})
        prev = count
    return finished_size("round_closed", trace, initial_stitches=payload["initial_stitches"],
                         gauge_stitches_per_10cm=20, gauge_rows_per_10cm=22)


def test_every_shape_is_offered_with_what_it_is_for():
    shapes = c.get("/api/shapes").json()["shapes"]
    by_id = {s["id"]: s for s in shapes}
    assert {"sphere", "egg", "cylinder", "limb", "cone", "disc", "dome"} <= set(by_id)
    for shape in shapes:
        assert shape["about"] and "(" in shape["about"]      # names a real part
    assert by_id["disc"]["flat"] is True
    assert by_id["sphere"]["flat"] is False
    assert by_id["sphere"]["height_ratio"] == 1.0            # a ball is as tall as it is wide
    assert by_id["limb"]["height_ratio"] > 2                 # a leg is long and thin


def test_a_ball_comes_out_a_ball_and_not_a_drum():
    d = make("sphere", 8, 8).json()
    counts = d["stitch_counts"]
    # It grows, holds briefly at its middle, and comes back down to be closed.
    assert counts[0] < max(counts) and counts[-1] < max(counts) / 4
    assert d["closed"] is True and d["final_stitches"] <= 8
    size = measured(d)
    assert abs(size["diameter_cm"] - 8) <= 0.6
    assert abs(size["height_cm"] - 8) <= 0.8
    # A drum would be as tall as its rounds stacked; a ball is nowhere near.
    assert size["height_if_stacked_cm"] > size["height_cm"] * 1.3


def test_the_old_browser_template_would_have_failed_that():
    """Six stitches added a round, straight, then six taken away: a drum.

    Kept as a test because it is the exact shape the app used to make, and the
    point of the endpoint is that it no longer can.
    """
    counts, cur = [], 6
    while cur < 48:
        cur += 6
        counts.append(cur)
    counts += [48] * 8
    while cur > 6:
        cur -= 6
        counts.append(cur)
    drum = measured({"initial_stitches": 6, "stitch_counts": counts})
    # A ball is about as tall as it is wide. That one is a tin of tuna: the
    # increases and decreases spread flat and only the straight middle has any
    # height at all, so 7.6 cm across comes out 3.6 cm tall.
    assert drum["height_cm"] / drum["diameter_cm"] < 0.6
    ball = make("sphere", drum["diameter_cm"]).json()
    made = measured(ball)
    assert 0.85 < made["height_cm"] / made["diameter_cm"] < 1.2


def test_a_flat_circle_stays_flat_and_is_never_closed():
    d = make("disc", 10, 0).json()
    assert d["open_end"] is True and d["closed"] is False
    counts = d["stitch_counts"]
    assert counts == sorted(counts)            # it only ever grows
    size = measured(d)
    assert abs(size["diameter_cm"] - 10) <= 0.8
    assert size["lies_flat"] is True


def test_a_limb_is_a_long_tube_left_open_to_sew_on():
    d = make("limb", 4, 12).json()
    assert d["closed"] is False
    size = measured(d)
    assert abs(size["height_cm"] - 12) <= 1.0
    assert abs(size["diameter_cm"] - 4) <= 0.5


def test_the_height_is_suggested_when_none_is_given():
    """Nobody should have to know how tall a ball is."""
    asked = make("sphere", 9).json()
    assert asked["asked_height_cm"] == 9.0
    assert abs(make("limb", 4).json()["asked_height_cm"] - 10.0) < 0.01


def test_a_bigger_ball_needs_more_rounds_and_more_stitches():
    small, large = make("sphere", 6).json(), make("sphere", 12).json()
    assert large["widest_stitches"] > small["widest_stitches"] * 1.8
    assert len(large["rounds"]) > len(small["rounds"])


def test_every_round_consumes_exactly_what_the_last_one_made():
    """The chain has to hold, or the rounds editor shows errors on arrival."""
    for archetype in ("sphere", "egg", "cylinder", "limb", "cone", "dome", "disc"):
        d = make(archetype, 8).json()
        prev = d["initial_stitches"]
        for round_, expected in zip(d["rounds"], d["stitch_counts"]):
            ops = round_["operations"]
            consumed = sum(n * (2 if op.endswith("2TOG") else 1) for op, n in ops.items())
            made = sum(n * (2 if op.endswith("_INC") else 1) for op, n in ops.items()
                       if not op.endswith("2TOG"))
            made += sum(n for op, n in ops.items() if op.endswith("2TOG"))
            assert consumed == prev, f"{archetype}: round consumes {consumed}, had {prev}"
            assert made == expected, f"{archetype}: round makes {made}, wanted {expected}"
            prev = expected


def test_it_says_what_is_wrong_in_words_a_person_can_act_on():
    for body, wanted in [
        ({"archetype": "banana", "width_cm": 8, **GAUGE}, "not a shape"),
        ({"archetype": "sphere", "width_cm": 0, **GAUGE}, "how wide"),
        ({"archetype": "sphere", "width_cm": 8, "gauge_stitches_per_10cm": 0,
          "gauge_rows_per_10cm": 22}, "gauge"),
        ({"archetype": "sphere", "width_cm": 8, "stitch": "NONSENSE", **GAUGE}, "not a stitch"),
    ]:
        r = c.post("/api/shapes/rounds", json=body)
        assert r.status_code == 422
        message = r.json()["detail"]["message"]
        assert wanted in message
        assert "{" not in message and "_" not in message      # never engine-speak


def test_a_piece_can_be_worked_in_a_stitch_other_than_single_crochet():
    d = make("sphere", 10, stitch="DC").json()
    used = {op for round_ in d["rounds"] for op in round_["operations"]}
    assert used <= {"DC", "DC_INC", "DC2TOG"}
