"""Colours over the API: chosen from the catalogue, never typed in."""
from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)

SPEC = {
    "object": "teddy bear", "total_height_cm": 24,
    "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
    "yarn_id": "YARNSMITHS_DK", "hook_mm": 3.0, "allowance_percent": 10,
    "parts": [
        {"name": "Head", "category": "HEAD", "height_fraction": 0.34, "width_fraction": 0.34},
        {"name": "Arm", "category": "LIMB", "height_fraction": 0.28, "width_fraction": 0.09, "copies": 2},
    ],
}


def test_the_catalogue_is_served_and_every_entry_is_a_real_colour():
    body = c.get("/api/colours").json()
    assert len(body["colours"]) >= 60
    names = {x["name"] for x in body["colours"]}
    assert {"Cream", "Teal", "Charcoal"} <= names
    for x in body["colours"]:
        assert x["hex"].startswith("#") and x["colour_id"]


def test_a_yarn_gets_its_own_card_first_and_the_palette_behind_it():
    body = c.get("/api/colours", params={"yarn_id": "YARNSMITHS_DK"}).json()
    assert body["yarn_id"] == "YARNSMITHS_DK"
    # No manufacturer shade card has been captured yet, so the palette is all
    # there is -- but the shape of the answer is what the picker relies on.
    assert body["yarn_specific_count"] == sum(1 for x in body["colours"] if x["yarn_specific"])
    assert len(body["colours"]) >= 60


def test_a_chosen_shade_is_carried_onto_the_design_and_every_part():
    d = c.post("/api/design/generate", json={**SPEC, "colour_id": "PAL_CML"}).json()
    assert d["colour"]["name"] == "Camel" and d["colour"]["hex"] == "#B08954"
    assert d["colour_source"] == "chosen"
    assert all(p["colour"]["colour_id"] == "PAL_CML" for p in d["parts"])


def test_an_unknown_colour_is_refused_rather_than_stored():
    r = c.post("/api/design/generate", json={**SPEC, "colour_id": "#ff0000"})
    assert r.status_code == 422
    assert "colour_id" in r.json()["detail"]


def test_a_design_without_a_colour_says_so_instead_of_guessing():
    d = c.post("/api/design/generate", json=SPEC).json()
    assert d["colour"] is None and d["colour_source"] == "not set"
    assert all(p["colour"] is None for p in d["parts"])


def test_a_yarn_with_a_captured_card_offers_its_own_shades_first():
    body = c.get("/api/colours", params={"yarn_id": "YARNSMITHS_DK"}).json()
    own = [x for x in body["colours"] if x["yarn_specific"]]
    assert body["yarn_specific_count"] == 120 == len(own)
    # the maker's own card comes first, in the shade-code order it is printed in
    assert [x["colour_id"] for x in body["colours"][:120]] == [x["colour_id"] for x in own]
    assert [x["code"] for x in own] == sorted(x["code"] for x in own)
    black = next(x for x in own if x["code"] == "3000")
    assert black["name"] == "Black" and black["hex"] == "#080904"
    # and the generic palette is still there behind it
    assert any(x["colour_id"].startswith("PAL_") for x in body["colours"])


def test_a_shade_from_the_makers_card_can_be_chosen_for_a_design():
    d = c.post("/api/design/generate",
               json={**SPEC, "colour_id": "YARNSMITHS_DK__3208"}).json()
    assert d["colour"]["name"] == "Bottle Green"
    assert d["colour"]["yarn_specific"] is True
    assert all(p["colour"]["hex"] == d["colour"]["hex"] for p in d["parts"])
