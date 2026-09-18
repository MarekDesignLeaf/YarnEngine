"""The shade catalogue, and matching a described colour onto it.

The rule these guard: a colour in the app is always a row in the catalogue.
Matching may fail and return nothing, but it may never invent a shade.
"""
from pathlib import Path

import pytest

from src.library.colours import load_palette, match_colour

ROOT = Path(__file__).resolve().parents[2]
PALETTE = load_palette(ROOT)


def test_the_palette_loads_as_valid_catalogue_rows():
    assert len(PALETTE) >= 60
    ids = [c["colour_id"] for c in PALETTE]
    assert len(ids) == len(set(ids))
    for c in PALETTE:
        assert c["yarn_id"] is None                 # the generic fallback card
        assert c["hex"].startswith("#") and len(c["hex"]) == 7
        int(c["hex"][1:], 16)                       # raises if not a colour
        assert c["name"] and c["family"] and c["source_type"] == "standard_palette"


@pytest.mark.parametrize("described,expected", [
    ("teal", "Teal"),
    ("Forest Green", "Forest green"),
    ("baby blue", "Baby blue"),
    ("charcoal grey", "Charcoal"),          # the shade, not the family
    ("soft baby pink yarn", "Baby pink"),   # the phrase inside a sentence
    ("honey mustard", "Mustard"),
    ("light brown", "Camel"),               # not "Light grey"
    ("dark green", "Forest green"),         # the modifier picks within a family
    ("pale blue", "Baby blue"),
])
def test_described_colours_land_on_the_right_shade(described, expected):
    assert match_colour(described, PALETTE)["name"] == expected


@pytest.mark.parametrize("described", ["", None, "sparkly", "self-striping", "12345"])
def test_nothing_is_invented_when_the_description_says_no_colour(described):
    assert match_colour(described, PALETTE) is None


def test_a_match_is_always_a_catalogue_row():
    got = match_colour("dark red", PALETTE)
    assert got in PALETTE
