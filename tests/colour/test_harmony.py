"""Colour schemes: the maths, and the promise that nothing is invented."""
import pytest

from src.colour.harmony import (build_palette, contrast_ratio, delta_e, hex_to_lab,
                                lab_to_lch, SCHEMES)

# A small stand-in for a manufacturer's card.
CARD = [
    {"colour_id": "C1", "code": "01", "name": "Grass", "hex": "#57a56c", "family": "Green"},
    {"colour_id": "C2", "code": "02", "name": "Rose", "hex": "#ba6a9a", "family": "Pink"},
    {"colour_id": "C3", "code": "03", "name": "Cream", "hex": "#f1ead8", "family": "Neutral"},
    {"colour_id": "C4", "code": "04", "name": "Ink", "hex": "#10151f", "family": "Neutral"},
    {"colour_id": "C5", "code": "05", "name": "Sky", "hex": "#6c99cf", "family": "Blue"},
    {"colour_id": "C6", "code": "06", "name": "Moss", "hex": "#2b8a55", "family": "Green"},
    {"colour_id": "C7", "code": "07", "name": "Mint", "hex": "#aed0b6", "family": "Green"},
]


def test_the_colour_maths_matches_the_published_values():
    assert hex_to_lab("#ffffff")[0] == pytest.approx(100, abs=0.01)
    assert hex_to_lab("#000000")[0] == pytest.approx(0, abs=0.01)
    light, chroma, hue = lab_to_lch(hex_to_lab("#ff0000"))
    assert (light, chroma, hue) == pytest.approx((53.24, 104.55, 40.0), abs=0.1)
    assert delta_e(hex_to_lab("#ff0000"), hex_to_lab("#ff0000")) == 0
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=0.01)
    with pytest.raises(ValueError):
        hex_to_lab("not a colour")


def test_every_colour_offered_is_one_from_the_card():
    """The whole point: a scheme you can order, not a scheme you can admire."""
    card_hexes = {row["hex"] for row in CARD}
    for scheme in SCHEMES:
        result = build_palette(CARD[0], CARD, scheme=scheme, count=4)
        assert len(result["palette"]) >= 2
        for entry in result["palette"]:
            assert entry["hex"] in card_hexes
            assert entry["colour_id"] in {row["colour_id"] for row in CARD}
        ids = [e["colour_id"] for e in result["palette"]]
        assert len(ids) == len(set(ids)), "the same shade must not fill two places"


def test_the_ideal_is_shown_next_to_what_was_actually_found():
    result = build_palette(CARD[0], CARD, scheme="complementary")
    partner = result["palette"][1]
    assert partner["name"] == "Rose"                      # the card's nearest to green's opposite
    assert partner["ideal_hex"].startswith("#")           # what the wheel asked for
    assert partner["ideal_hex"] not in {row["hex"] for row in CARD}
    assert partner["distance"] > 0 and partner["exact"] is False


def test_a_toy_gets_a_body_a_muzzle_and_a_dark_detail():
    result = build_palette(CARD[0], CARD, scheme="amigurumi")
    names = [e["name"] for e in result["palette"]]
    assert names[0] == "Grass"
    assert "Cream" in names and "Ink" in names
    assert "muzzle" in result["palette"][1]["role"]


def test_shades_that_would_blur_together_are_called_out():
    result = build_palette(CARD[0], CARD, scheme="analogous", count=4)
    pairs = {(p["a"], p["b"]): p for p in result["pairs"]}
    assert all(p["difference"] >= 0 for p in pairs.values())
    близко = build_palette(CARD[5], [CARD[5], CARD[0]], scheme="analogous", count=2)
    assert any("read as one colour" in note for note in близко["notes"])


def test_a_grey_base_is_told_the_truth_about_colour_wheels():
    grey = {"colour_id": "G", "code": "99", "name": "Slate", "hex": "#9a9a9c", "family": "Grey"}
    result = build_palette(grey, CARD + [grey], scheme="triadic")
    assert any("nothing to say about a neutral" in note for note in result["notes"])


def test_a_card_with_no_partner_in_that_part_of_the_wheel_says_so():
    greens_only = [CARD[0], CARD[5], CARD[6]]
    result = build_palette(CARD[0], greens_only, scheme="complementary")
    assert any("closest it gets" in note for note in result["notes"])
    assert result["palette"][1]["hex"] in {r["hex"] for r in greens_only}


def test_an_unknown_scheme_is_refused():
    with pytest.raises(ValueError):
        build_palette(CARD[0], CARD, scheme="vibes")
