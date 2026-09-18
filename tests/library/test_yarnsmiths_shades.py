"""The Yarnsmiths shade cards, as read from each range's own page.

These guard the capture rather than the website: every shade must belong to a
yarn that is actually in the library, carry a real colour, and keep the code
the maker prints on the ball band. If a re-capture mangles a card, these fail
instead of quietly changing what the app shows as "Bottle Green".
"""
import json
import re
from pathlib import Path

import pytest

from src.library.colours import family_of, load_shade_cards

ROOT = Path(__file__).resolve().parents[2]
CARDS = sorted((ROOT / "data/colours/yarnsmiths").glob("*.json"))
YARN_IDS = {p.stem for p in (ROOT / "data/yarns").glob("YARNSMITHS_*.json")}
ROWS = load_shade_cards(ROOT)


def test_every_range_in_the_library_has_its_shade_card():
    assert len(CARDS) == 53
    assert {p.stem for p in CARDS} == YARN_IDS
    assert len(ROWS) == 1844


@pytest.mark.parametrize("path", CARDS, ids=lambda p: p.stem)
def test_each_card_belongs_to_a_yarn_and_every_shade_is_complete(path):
    card = json.loads(path.read_text())
    assert card["record_type"] == "yarn_shade_card"
    assert card["yarn_id"] == path.stem and card["yarn_id"] in YARN_IDS
    assert card["brand"] == "Yarnsmiths"
    assert card["source_reference"].startswith("https://www.woolwarehouse.co.uk/yarn/yarnsmiths-")
    assert card["shades"]
    codes = [s["code"] for s in card["shades"]]
    assert len(codes) == len(set(codes)), "a shade code is listed twice"
    for shade in card["shades"]:
        assert shade["name"].strip() == shade["name"] and shade["name"]
        assert re.fullmatch(r"#[0-9a-f]{6}", shade["hex"]), shade
        assert shade["sku"].endswith(shade["code"])
        assert not shade["code"].startswith("*")      # the site's own markers, stripped


def test_the_yarn_a_card_names_matches_the_page_it_came_from():
    for path in CARDS:
        card = json.loads(path.read_text())
        yarn = json.loads((ROOT / "data/yarns" / f"{card['yarn_id']}.json").read_text())
        assert card["source_reference"] == yarn["source_reference"]
        assert card["product"] == yarn["product"]


def test_shades_are_catalogue_rows_tied_to_their_own_yarn():
    by_yarn = {}
    for row in ROWS:
        assert row["yarn_id"] in YARN_IDS
        assert row["source_type"] == "manufacturer_web"
        by_yarn.setdefault(row["yarn_id"], []).append(row)
    assert len(by_yarn["YARNSMITHS_DK"]) == 120
    assert len({r["colour_id"] for r in ROWS}) == len(ROWS)


def test_colours_are_not_all_the_same_and_cover_the_spectrum():
    # a sampling bug that returned the background or one constant would show here
    assert len({r["hex"] for r in ROWS}) > 1200
    families = {r["family"] for r in ROWS}
    assert {"Red", "Orange", "Yellow", "Green", "Blue", "Purple",
            "Pink", "Brown", "Grey", "Neutral"} <= families


@pytest.mark.parametrize("hex_value,expected", [
    ("#132a1a", "Green"),    # bottle green: dark, but not black
    ("#080904", "Neutral"),  # black
    ("#f8f4ea", "Neutral"),  # white
    ("#908d7a", "Neutral"),  # a warm natural, not a colour
    ("#d2cec8", "Neutral"),  # a warm pale silver reads as a natural
    ("#66707a", "Grey"),     # a true, cool grey
    ("#6a411d", "Brown"),
    ("#b80c0f", "Red"),
    ("#fa8214", "Orange"),
    ("#eeca55", "Yellow"),
    ("#09686a", "Blue"),     # teal sits with the blues, as the palette does
    ("#7c2488", "Purple"),
    ("#e95f96", "Pink"),
])
def test_a_measured_colour_lands_in_the_family_a_person_would_say(hex_value, expected):
    assert family_of(hex_value) == expected


def test_named_shades_look_like_their_names():
    dk = {s["name"]: s["hex"] for s in
          json.loads((ROOT / "data/colours/yarnsmiths/YARNSMITHS_DK.json").read_text())["shades"]}
    assert family_of(dk["Black"]) == "Neutral" and dk["Black"] < "#303030"
    assert family_of(dk["White"]) == "Neutral" and dk["White"] > "#e0e0e0"
    assert family_of(dk["Bright Red"]) == "Red"
    assert family_of(dk["Royal Blue"]) == "Blue"
    assert family_of(dk["Grass Green"]) == "Green"
