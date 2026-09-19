"""One round becoming several — legs, arms, tentacles — and several becoming one.

The arithmetic is small. What it has to get right is the chains that bridge
the gaps, because those are stitches: they land in the new round's count and
they eat yarn, and leaving them out is how a body comes out short.
"""
import pytest

from src.construction.branching import MODES, even_shares, join, listing, plan, sewn, split


def test_two_legs_worked_straight_into_a_body():
    """The classic. Twelve and twelve is twenty-four, and nothing else."""
    made = join([12, 12])
    assert made["valid"] and made["stitches"] == 24
    assert made["operations"] == {"SC": 24}
    assert "(24)" in made["line"]
    # It admits that a tight join leaves a gap to close by hand.
    assert any("close by hand" in n for n in made["notes"])


def test_the_chains_across_the_gap_are_counted_once_per_gap():
    """Two legs meet in two places, front and back.

    Counting the chains once gives a body two stitches short, which is the
    error this exists to stop.
    """
    made = join([12, 12], chains_between=2)
    assert made["crossings"] == 2
    assert made["stitches"] == 24 + 2 * 2 == 28
    assert made["operations"] == {"SC": 24, "CH": 4}
    assert made["line"].count("ch 2") == 2
    # three pieces meet in three places
    assert join([10, 10, 10], chains_between=2)["stitches"] == 36


def test_skipping_where_the_pieces_touch_takes_stitches_off_both_sides():
    made = join([12, 12], skip_each_side=1)
    assert made["stitches"] == 24 - 2 * 2 * 1 == 20
    assert made["operations"]["SC"] == 20
    assert "skipping 1 stitch at each side" in made["how"]


def test_it_will_not_skip_a_piece_out_of_existence():
    made = join([3, 12], skip_each_side=2)
    assert not made["valid"]
    assert "Piece 1 has only 3 stitches" in made["issues"][0]


def test_splitting_gives_each_piece_its_share_plus_its_chains():
    """44 split in half with two chains is two tubes of 24, not of 22."""
    made = split(44, [22, 22], chains_between=2)
    assert made["valid"] and made["branches"] == [24, 24]
    assert made["operations"] == {"SC": 44, "CH": 4}
    assert made["lines"] == ["piece 1: 22 sts + ch 2 across the gap (24)",
                             "piece 2: 22 sts + ch 2 across the gap (24)"]


def test_every_stitch_has_to_go_somewhere():
    made = split(44, [20, 20], chains_between=2)
    assert not made["valid"]
    assert "add up to 40" in made["issues"][0] and "44 stitches" in made["issues"][0]


def test_a_piece_too_thin_to_work_in_the_round_is_said_so_not_produced():
    made = split(6, [2, 2, 2])
    assert not made["valid"]
    assert all("cannot be worked in the round" in i for i in made["issues"])
    # and one that is merely fiddly is allowed, with the honest advice
    fiddly = split(10, [5, 5])
    assert fiddly["valid"]
    assert any("sew it on" in n for n in fiddly["notes"])


def test_a_remainder_is_spread_rather_than_dumped_on_the_last_piece():
    """Otherwise one leg comes out three stitches fatter than the other."""
    assert even_shares(45, 2) == [23, 22]
    assert even_shares(44, 3) == [15, 15, 14]
    assert sum(even_shares(37, 4)) == 37
    assert max(even_shares(37, 4)) - min(even_shares(37, 4)) <= 1


def test_tentacles_are_separate_pieces_and_it_says_so():
    """An octopus's tentacles are not split off anything, and the app should
    not pretend otherwise just because it can do arithmetic."""
    made = sewn([8] * 8)
    assert made["valid"] and made["stitches"] is None and made["operations"] == {}
    assert "its own piece" in made["how"]
    assert "sewn" in {m["id"] for m in listing()}
    assert MODES["sewn"]["continuous"] is False


def test_the_three_ways_are_named_the_way_a_maker_would_name_them():
    for mode in listing():
        assert mode["name"] and mode["about"] and mode["examples"]
        assert not any(c in mode["about"] for c in "{}_")
        assert mode["minimum_stitches"] >= 4


def test_plan_answers_all_three_in_the_same_shape():
    for payload in [{"mode": "sewn", "parts": [8, 8]},
                    {"mode": "joined", "parts": [12, 12], "chains_between": 2},
                    {"mode": "split", "stitches": 44, "pieces": 2, "chains_between": 2}]:
        made = plan(payload)
        assert made["valid"] and made["how"] and made["name"] and made["about"]
        assert isinstance(made["operations"], dict) and isinstance(made["notes"], list)
    assert plan({"mode": "wibble"})["valid"] is False


def test_asked_for_pieces_rather_than_shares_it_divides_them_evenly():
    made = plan({"mode": "split", "stitches": 45, "pieces": 2, "chains_between": 2})
    assert made["shares"] == [23, 22] and made["branches"] == [25, 24]


def test_a_piece_can_be_worked_in_a_stitch_other_than_single_crochet():
    assert join([12, 12], stitch="DC")["operations"] == {"DC": 24}


def test_nothing_it_says_is_written_in_engine_words():
    for payload in [{"mode": "joined", "parts": [12, 12], "chains_between": 2},
                    {"mode": "split", "stitches": 44, "pieces": 2},
                    {"mode": "split", "stitches": 6, "pieces": 3},
                    {"mode": "sewn", "parts": [8]}]:
        made = plan(payload)
        for sentence in [made["how"], *made["notes"], *made["issues"]]:
            assert sentence[0].isupper() and sentence.rstrip().endswith((".", "!"))
            assert "_" not in sentence and "{" not in sentence
