"""Constructions: what a stitch count means depends on how the piece is built."""
import math

import pytest

from src.construction.types import (CONSTRUCTIONS, finished_size, get, listing, start_issue)

GROWING = [{"output_stitches": n} for n in (12, 18, 24, 30, 30, 30, 24, 18)]


def test_the_same_stitch_counts_mean_different_things():
    """Sixty stitches is 30 cm across flat and 19 cm of diameter in the round.
    That difference is the whole reason constructions exist."""
    flat = [{"output_stitches": 60}] * 10
    made = {c: finished_size(c, flat, gauge_stitches_per_10cm=20, gauge_rows_per_10cm=22)
            for c in ("round_closed", "flat_rows")}
    assert made["flat_rows"]["width_cm"] == 30.0
    assert made["round_closed"]["diameter_cm"] == round(30.0 / math.pi, 1)
    assert made["round_closed"]["circumference_cm"] == 30.0
    # and both are the same height, because rows are rows
    assert made["flat_rows"]["length_cm"] == made["round_closed"]["height_cm"]


def test_an_open_tube_is_measured_round_not_across():
    tube = finished_size("round_open", [{"output_stitches": 48}] * 30,
                         gauge_stitches_per_10cm=20, gauge_rows_per_10cm=22)
    assert "cm long" in tube["summary"] and "around" in tube["summary"]
    assert tube["circumference_cm"] == 24.0


def test_a_shaped_panel_gives_both_ends_of_its_range():
    shawl = finished_size("flat_shaped", [{"output_stitches": n} for n in range(6, 40, 2)],
                          gauge_stitches_per_10cm=20, gauge_rows_per_10cm=22)
    assert shawl["narrowest_width_cm"] == 3.0 and shawl["width_cm"] == 19.0
    assert "3.0–19.0 cm across" in shawl["summary"]
    assert len(shawl["outline"]) == 17          # the width of every row, for drawing it


def test_a_branched_piece_admits_it_has_no_single_size():
    branched = finished_size("branched", GROWING,
                             gauge_stitches_per_10cm=20, gauge_rows_per_10cm=22)
    assert branched["known"] is False
    assert "each branch has its own" in branched["summary"]
    assert branched.get("width_cm") is None


def test_motifs_are_measured_by_their_layout():
    blanket = finished_size("motif_joined", [{"output_stitches": 12}] * 10,
                            gauge_stitches_per_10cm=14, gauge_rows_per_10cm=14,
                            layout={"across": 7, "down": 10, "motif_cm": 15,
                                    "join_cm": 1, "border_cm": 5})
    assert blanket["motifs"] == 70
    assert blanket["width_cm"] == 7 * 15 + 6 * 1 + 10
    assert blanket["height_cm"] == 10 * 15 + 9 * 1 + 10


def test_how_a_piece_starts_is_the_rule_a_construction_imposes():
    assert start_issue("round_closed", 6, 6) is None          # the ring is its starting stitches
    assert start_issue("round_closed", 0, 6)["code"] == "CLOSED_START_HAS_NOTHING_TO_WORK_INTO"
    assert start_issue("round_closed", 0, 0) is None          # a first round that makes its own
    assert start_issue("flat_rows", 0, 0)["code"] == "START_STITCHES_REQUIRED"
    assert start_issue("round_open", 48, 48) is None


def test_the_old_program_types_still_mean_what_they_meant():
    assert get("amigurumi").id == "round_closed"
    assert get("branch").id == "branched"
    assert get(None).id == "round_closed"
    with pytest.raises(KeyError):
        get("wishes")


def test_each_construction_says_enough_to_be_offered_in_a_list():
    for row in listing():
        assert row["name"] and row["about"] and row["examples"]
        assert row["row_word"] in ("round", "row")
        assert row["start_label"]
    assert "branched" not in {c["id"] for c in listing("crochet")}   # knitting only
    assert {"round_closed", "flat_rows"} <= {c["id"] for c in listing("crochet")}


def test_nothing_is_measured_without_a_gauge():
    with pytest.raises(ValueError):
        finished_size("flat_rows", GROWING, gauge_stitches_per_10cm=0, gauge_rows_per_10cm=22)
    empty = finished_size("flat_rows", [], gauge_stitches_per_10cm=20, gauge_rows_per_10cm=22)
    assert empty["known"] is False
