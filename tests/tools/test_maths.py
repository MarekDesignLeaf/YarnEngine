"""The back-of-an-envelope sums, and the cases that catch people out."""
from pathlib import Path

import pytest

from src.tools.maths import (change_to_target, convert_size, convert_units,
                             plan_squares, size_from_gauge, spread_evenly, yarn_amount)

ROOT = Path(__file__).resolve().parents[2]


def test_a_round_that_divides_evenly_is_written_as_one_repeat():
    result = spread_evenly(48, 6)
    assert result["instruction"] == "[7 sc, inc] x 6 (54)"
    assert result["to_stitches"] == 54 and result["even"] is True
    assert result["operations"] == {"SC_INC": 6, "SC": 42}
    assert result["note"] is None


def test_a_round_that_does_not_divide_is_split_honestly():
    """50 with 6 increases is not six groups of eight — it is two and four."""
    result = spread_evenly(50, 6)
    assert result["instruction"] == "[8 sc, inc] x 2, [7 sc, inc] x 4 (56)"
    assert result["even"] is False and "does not divide" in result["note"]
    worked = sum(g["plain"] * g["times"] + g["times"] for g in result["groups"])
    assert worked == 50, "the round has to use every stitch there is"


def test_decreases_eat_two_stitches_each():
    result = spread_evenly(48, -6)
    assert result["instruction"] == "[6 sc, dec] x 6 (42)"
    assert result["operations"] == {"SC2TOG": 6, "SC": 36}
    assert 6 * 2 + 36 == 48


@pytest.mark.parametrize("stitches,change,says", [
    (10, -6, "the most this round can lose is 5"),
    (6, 8, "the most this round can add"),
    (10, 0, "how many stitches to add or remove"),
])
def test_impossible_rounds_are_refused_with_the_reason(stitches, change, says):
    with pytest.raises(ValueError) as caught:
        spread_evenly(stitches, change)
    assert says in str(caught.value)


def test_the_same_sum_asked_as_a_target():
    assert change_to_target(36, 48)["instruction"] == "[2 sc, inc] x 12 (48)"
    with pytest.raises(ValueError):
        change_to_target(36, 36)


def test_measurements_come_back_as_what_whole_stitches_make():
    result = size_from_gauge(20, 22, width_cm=25, height_cm=30)
    assert result["stitches"] == 50 and result["rows"] == 66
    assert result["width_cm"] == 25.0
    odd = size_from_gauge(21, 22, width_cm=25)
    assert odd["stitches"] == 53                       # 52.5 rounded
    assert odd["width_off_by_cm"] != 0                 # and it says what that costs
    with pytest.raises(ValueError):
        size_from_gauge(0, 22, width_cm=10)
    with pytest.raises(ValueError):
        size_from_gauge(20, 22)                        # nothing to work from


def test_hook_sizes_come_from_the_published_table():
    four = convert_size(ROOT, "hook", mm=4.0)
    assert four["exact"] and four["size"] == {"mm": 4.0, "us": "G-6", "uk": "8"}
    assert convert_size(ROOT, "hook", us="H-8")["size"]["mm"] == 5.0
    assert convert_size(ROOT, "needle", mm=4.0)["size"]["us"] == "6"
    assert "craftyarncouncil" in four["sources"]["metric_us"]["url"]


def test_a_size_not_on_the_chart_is_not_quietly_rounded():
    odd = convert_size(ROOT, "hook", mm=4.1)
    assert odd["exact"] is False
    assert [r["mm"] for r in odd["nearest"]] == [4.0, 4.25]
    assert "not a size on the chart" in odd["note"]


def test_units_use_the_exact_factors():
    assert convert_units(100, "m")["yards"] == 109.36
    assert convert_units(1, "oz")["grams"] == 28.3
    with pytest.raises(ValueError):
        convert_units(1, "furlongs")


def test_length_and_weight_are_only_answered_for_a_stated_ball():
    result = yarn_amount(50, 80, length_m=120)
    assert result["mass_g"] == 75.0 and result["balls"] == 1.5
    back = yarn_amount(50, 80, mass_g=75)
    assert back["length_m"] == 120.0
    with pytest.raises(ValueError):
        yarn_amount(0, 80, length_m=10)


def test_a_blanket_is_a_whole_number_of_squares_and_says_what_that_measures():
    plan = plan_squares(120, 160, 15, border_cm=5)
    assert plan["across"] * plan["down"] == plan["squares"]
    assert plan["finished_width_cm"] == plan["across"] * 15 + 10
    assert plan["off_by_width_cm"] == plan["finished_width_cm"] - 120
    seamed = plan_squares(120, 160, 15, join_cm=1)
    assert seamed["finished_width_cm"] == seamed["across"] * 15 + (seamed["across"] - 1)


def test_the_square_programme_is_a_real_granny_square():
    plan = plan_squares(120, 160, 15, gauge_rows_per_10cm=14)
    rounds = plan["rounds_per_square"]
    assert plan["stitches_per_square"] == 6 * rounds * (rounds + 1)
    assert plan["program"]["initial_stitches"] == 12
    # every round has to consume exactly what the one before it produced
    stitches = 12
    for step in plan["program"]["rounds"]:
        ops = step["operations"]
        assert ops["DC"] + ops["DC_INC"] == stitches
        stitches = ops["DC"] + 2 * ops["DC_INC"]
