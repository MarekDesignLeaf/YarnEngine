import math

import pytest

from src.crochet.amigurumi import analyse_rounds
from src.design.parts import build_design, part_pattern, written_pattern, _round_text
from src.design.shapes import ARCHETYPES, profile_points, rounds_for_part
from src.design.vision import VisionUnavailable, describe_photo, validate_parts

# The real operation definitions the app validates rounds against, so these
# tests fail if a generated pattern would be rejected in production.
import json
from pathlib import Path

OPS = {r["operation_id"]: r for r in json.loads(
    (Path(__file__).resolve().parents[2] / "data/stitches/operations.seed.json").read_text())}

BEAR = {
    "object": "teddy bear", "total_height_cm": 24,
    "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
    "parts": [
        {"name": "Head", "category": "HEAD", "height_fraction": 0.33, "width_fraction": 0.33},
        {"name": "Body", "category": "BODY", "height_fraction": 0.42, "width_fraction": 0.30},
        {"name": "Arm", "category": "LIMB", "height_fraction": 0.28, "width_fraction": 0.09, "copies": 2},
        {"name": "Ear", "category": "EAR", "height_fraction": 0.09, "width_fraction": 0.09, "copies": 2},
    ],
}


def test_every_generated_part_is_a_valid_round_program():
    # The whole point of generating rather than guessing: the rounds must pass
    # the same analyser the editor uses, for every archetype and gauge.
    for archetype in ARCHETYPES:
        for gs, gr in [(20, 22), (14, 16), (26, 30)]:
            built = rounds_for_part(archetype, 8.0, 6.0, gs, gr)
            res = analyse_rounds({"initial_stitches": built["initial_stitches"],
                                  "rounds": built["rounds"]}, OPS)
            assert res["valid"], (archetype, gs, gr, res["issues"])
            assert res["final_stitches"] == built["final_stitches"]


def test_a_part_never_starts_by_decreasing():
    # A magic ring is the narrowest point; opening with a decrease is the
    # signature of walking the profile vertically instead of along the surface.
    for archetype in ARCHETYPES:
        built = rounds_for_part(archetype, 9.0, 7.0, 20, 22)
        first = built["rounds"][0]["operations"]
        assert "SC2TOG" not in first, (archetype, first)
        assert built["stitch_counts"][0] >= built["initial_stitches"], archetype


def test_a_ball_grows_and_closes_like_a_real_pattern():
    built = rounds_for_part("sphere", 8.0, 8.0, 20, 22)
    counts = built["stitch_counts"]
    assert counts[0] > 6 and max(counts) > 40
    assert counts == sorted(counts[:counts.index(max(counts)) + 1]) + counts[counts.index(max(counts)) + 1:]
    assert built["closed"] and built["final_stitches"] == 6   # cinched, not worked to nothing


def test_open_parts_are_left_open_and_closed_parts_are_cinched():
    arm = part_pattern({"name": "Arm", "category": "LIMB", "height_cm": 7, "width_cm": 2.2}, 20, 22)
    head = part_pattern({"name": "Head", "category": "HEAD", "height_cm": 8, "width_cm": 8}, 20, 22)
    assert "leaving a long tail" in arm["written"][-2]
    assert "draw the remaining" in head["written"][-2]


def test_size_follows_gauge_not_a_fixed_stitch_count():
    loose = rounds_for_part("sphere", 8.0, 8.0, 12, 13)
    tight = rounds_for_part("sphere", 8.0, 8.0, 28, 30)
    assert max(tight["stitch_counts"]) > max(loose["stitch_counts"])
    assert len(tight["rounds"]) > len(loose["rounds"])


def test_widest_round_matches_the_requested_width():
    built = rounds_for_part("sphere", 10.0, 10.0, 20, 22)
    stitch_w = 10 / 20
    widest_cm = max(built["stitch_counts"]) * stitch_w / math.pi   # circumference -> diameter
    assert abs(widest_cm - 10.0) < 1.0          # within a stitch or so of the target


def test_design_scales_parts_from_the_stated_height():
    small = build_design({**BEAR, "total_height_cm": 12})
    big = build_design({**BEAR, "total_height_cm": 30})
    assert small["parts"][0]["height_cm"] < big["parts"][0]["height_cm"]
    assert small["total_stitches"] < big["total_stitches"]
    assert big["piece_count"] == 6           # head, body, 2 arms, 2 ears


def test_written_pattern_reads_like_a_pattern():
    text = written_pattern(build_design(BEAR))
    assert "TEDDY BEAR" in text
    assert "HEAD — make 1" in text and "ARM — make 2" in text
    assert "R1: 6 sc in magic ring (6)" in text
    assert "sc in each st around" in text


def test_round_text_uses_repeats_and_states_the_count():
    assert _round_text({"SC": 12}, 12) == "sc in each st around (12)"
    assert _round_text({"SC": 12, "SC_INC": 6}, 24) == "[2 sc, inc] x 6 (24)"
    assert _round_text({"SC": 13, "SC_INC": 6}, 25) == "[2 sc, inc] x 6, sc (25)"
    assert _round_text({"SC": 10, "SC2TOG": 5}, 15) == "[2 sc, dec] x 5 (15)"
    assert _round_text({"SC_INC": 6}, 12) == "inc in each st around (12)"


def test_identical_rounds_are_collapsed_into_a_range():
    tube = part_pattern({"name": "Tube", "archetype": "cylinder",
                         "height_cm": 12, "width_cm": 4}, 20, 22)
    assert any("-" in line.split(":")[0] for line in tube["written"]), tube["written"]


def test_bad_input_is_refused():
    with pytest.raises(ValueError):
        build_design({**BEAR, "total_height_cm": 0})
    with pytest.raises(ValueError):
        build_design({**BEAR, "parts": []})
    with pytest.raises(ValueError):
        part_pattern({"name": "x", "archetype": "banana", "height_cm": 5}, 20, 22)
    with pytest.raises(ValueError):
        profile_points("sphere", 0, 5)


# --------------------------------------------------------------- vision ---

GOOD_REPLY = """Here you go:
```json
{"object":"teddy bear","confidence":"medium",
 "parts":[{"name":"Head","category":"HEAD","archetype":"sphere","copies":1,
           "height_fraction":0.33,"width_fraction":0.33,"colour":"brown","stuffed":true},
          {"name":"Arm","category":"LIMB","archetype":"limb","copies":2,
           "height_fraction":0.28,"width_fraction":0.09,"colour":"brown","stuffed":true}],
 "assembly":["Sew the head to the body."],
 "uncertain":["The back of the toy is not visible."]}
```"""


def test_vision_reply_is_parsed_and_only_usable_parts_are_kept():
    out = describe_photo([("image/png", b"x")], _transport=lambda body: GOOD_REPLY)
    assert out["object"] == "teddy bear"
    assert [p["name"] for p in out["parts"]] == ["Head", "Arm"]
    assert out["parts"][1]["copies"] == 2
    assert out["uncertain"]


def test_vision_output_drives_the_deterministic_generator():
    described = describe_photo([("image/png", b"x")], _transport=lambda body: GOOD_REPLY)
    design = build_design({"object": described["object"], "total_height_cm": 20,
                           "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
                           "parts": described["parts"]})
    for part in design["parts"]:
        res = analyse_rounds({"initial_stitches": part["initial_stitches"],
                              "rounds": part["rounds"]}, OPS)
        assert res["valid"], res["issues"]


def test_nonsense_from_the_model_is_rejected_not_built():
    raw = {"object": "thing", "parts": [
        {"name": "Bad shape", "archetype": "pyramid", "height_fraction": 0.5, "width_fraction": 0.5},
        {"name": "Impossible size", "archetype": "sphere", "height_fraction": 40, "width_fraction": 1},
        {"name": "Missing size", "archetype": "sphere"},
        {"name": "Fine", "archetype": "sphere", "height_fraction": 0.4, "width_fraction": 0.4, "copies": 1},
    ]}
    out = validate_parts(raw)
    assert [p["name"] for p in out["parts"]] == ["Fine"]
    assert len(out["dropped"]) == 3


def test_vision_failures_are_reported_not_guessed():
    with pytest.raises(VisionUnavailable):
        describe_photo([("image/png", b"x")], _transport=lambda body: "sorry, I can't see it")
    with pytest.raises(VisionUnavailable):
        describe_photo([], _transport=lambda body: GOOD_REPLY)
    with pytest.raises(VisionUnavailable):
        describe_photo([("image/tiff", b"x")], _transport=lambda body: GOOD_REPLY)
    with pytest.raises(VisionUnavailable):   # model returned only unusable parts
        describe_photo([("image/png", b"x")],
                       _transport=lambda body: '{"object":"x","parts":[{"name":"n","archetype":"pyramid"}]}')
