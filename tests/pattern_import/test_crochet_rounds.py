"""Reading somebody else's crochet pattern.

Written crochet is prose, so these are the forms people actually write, and
the forms that must fail loudly rather than quietly.
"""
import pytest

from src.pattern_import.crochet_rounds import looks_like_uk, parse_pattern


def counts(text, **kw):
    return parse_pattern(text, **kw).stitch_counts


def test_the_shorthand_form():
    p = parse_pattern("""R1: 6 sc in magic ring (6)
R2: inc in each st around (12)
R3: [sc, inc] x 6 (18)
R4: (2 sc, inc) 6 times (24)
R5: sc in each st around (24)
R6: [2 sc, dec] x 6 (18)""")
    assert p.initial_stitches == 6
    assert p.stitch_counts == [6, 12, 18, 24, 24, 18]
    assert p.rounds[2]["operations"] == {"SC": 12, "SC_INC": 6}
    assert p.issues == []


def test_the_written_out_form_a_beginner_pattern_uses():
    p = parse_pattern("""Round 1: Work 6 single crochet into a magic ring.
Round 2: Work 6 increases (2 single crochet in each stitch). You will have a total of 12 stitches.
Round 3: Work (1 single crochet, 1 increase) and repeat this 6 times around. You will have 18 stitches.
Round 4: Work 1 single crochet in each stitch around. You will have 18 stitches.""")
    assert p.stitch_counts == [6, 12, 18, 18] and p.issues == []


def test_asterisk_repeats_and_ranges_of_rounds():
    p = parse_pattern("""Rnd 1: 6 sc in magic ring -- 6 sts
Rnd 2: 2 sc in each st around -- 12 sts
Rnd 3-5: sc in each st around -- 12 sts
Rnd 6: *sc, dec; rep from * around -- 8 sts""")
    assert p.stitch_counts == [6, 12, 12, 12, 12, 8]
    assert len(p.rounds) == 5           # the range became three rounds
    assert p.issues == []


def test_repeat_around_without_brackets():
    p = parse_pattern("""R1: 6 sc in magic ring (6)
R2: inc in each around (12)
R3: sc in next 2 sts, inc; repeat around (16)""")
    assert p.stitch_counts == [6, 12, 16] and p.issues == []


def test_uk_terms_are_a_different_fabric_not_a_spelling():
    uk = parse_pattern("""Rnd 1: 6 dc into a magic ring (6)
Rnd 2: 2 dc in each st around (12)""", dialect="uk")
    assert uk.rounds[0]["operations"] == {"SC_INC": 6}      # UK dc is US sc
    us = parse_pattern("""Rnd 1: 6 dc into a magic ring (6)
Rnd 2: 2 dc in each st around (12)""")
    assert us.rounds[0]["operations"] == {"DC_INC": 6}      # same words, taller stitch


def test_a_uk_pattern_read_as_us_is_flagged_rather_than_reinterpreted():
    p = parse_pattern("Rnd 1: 6 htr into a magic ring (6)\nRnd 2: 2 htr in each st (12)")
    assert any("UK terms" in n for n in p.notes)
    assert looks_like_uk("htr, dtr") and not looks_like_uk("sc, hdc")


@pytest.mark.parametrize("line,expect", [
    ("R2: work some fancy puff thing around", "could not read"),
    ("R2: [sc, wiggle] x 6", "repeat could not be read"),
])
def test_what_cannot_be_read_is_reported_not_guessed(line, expect):
    p = parse_pattern(f"R1: 6 sc in magic ring (6)\n{line}")
    assert len(p.rounds) == 0
    assert expect in p.issues[0].reason
    assert p.issues[0].text == line


def test_a_stitch_count_that_disagrees_with_the_instructions_is_called_out():
    p = parse_pattern("R1: 6 sc in magic ring (6)\nR2: inc in each st around (14)")
    assert "says 14" in p.issues[0].reason and "make 12" in p.issues[0].reason


def test_a_round_that_does_not_use_up_the_previous_one_is_called_out():
    p = parse_pattern("R1: 6 sc in magic ring (6)\nR2: sc x 4 (4)")
    assert "uses 4 stitches but the previous round left 6" in p.issues[0].reason


def test_an_open_ended_round_that_does_not_divide_is_refused():
    p = parse_pattern("R1: 7 sc in magic ring (7)\nR2: [sc, inc] around")
    assert "does not come out evenly" in p.issues[0].reason


def test_prose_around_the_pattern_is_ignored_not_mistaken_for_rounds():
    p = parse_pattern("""HEAD
Use a 3 mm hook and stuff firmly.
Round 1: 6 sc in magic ring (6)
Round 2: inc in each st around (12)
Fasten off, leaving a long tail for sewing.""")
    assert p.stitch_counts == [6, 12] and p.issues == []


def test_a_pattern_with_no_magic_ring_still_starts_somewhere():
    p = parse_pattern("R1: ch 6 (6)\nR2: sc in each st around (6)")
    assert p.initial_stitches == 6
    assert any("No magic ring" in n for n in p.notes)
