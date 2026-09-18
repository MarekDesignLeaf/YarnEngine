"""Weights, checked the way a person would check them.

Written after a report that "everything shows 8 g". These pin the arithmetic
down so a wrong weight has to fail here rather than be argued about: grams are
metres times the yarn's own grams-per-metre, they scale with the piece, they
differ between yarns, and a bigger part always costs more than a smaller one.
"""
import pytest
from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)

BASE = {
    "object": "teddy bear",
    "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
    "hook_mm": 3.0, "allowance_percent": 10,
    "parts": [
        {"name": "Head", "category": "HEAD", "height_fraction": 0.34, "width_fraction": 0.34},
        {"name": "Body", "category": "BODY", "height_fraction": 0.40, "width_fraction": 0.40},
        {"name": "Arm", "category": "LIMB", "height_fraction": 0.28, "width_fraction": 0.09, "copies": 2},
        {"name": "Ear", "category": "EAR", "height_fraction": 0.10, "width_fraction": 0.10, "copies": 2},
    ],
}


def design(**over):
    r = c.post("/api/design/generate",
               json={**BASE, "total_height_cm": 24, "yarn_id": "YARNSMITHS_DK", **over})
    assert r.status_code == 200, r.text
    return r.json()


def test_grams_are_metres_times_the_yarns_own_grams_per_metre():
    d = design()
    g_per_m = d["yarn"]["g_per_m"]
    assert g_per_m == pytest.approx(d["yarn"]["tex"] / 1000.0, abs=5e-5)
    assert d["yarn"]["mass_g"] == pytest.approx(d["yarn"]["length_m"] * g_per_m, rel=0.02)
    for part in d["parts"]:
        y = part["yarn"]
        assert y["mass_g_total"] == pytest.approx(y["length_m_total"] * g_per_m, rel=0.02)
        assert y["mass_g_total"] == round(y["mass_g_each"] * part["copies"], 1)
        assert y["length_m_total"] == round(y["length_m_each"] * part["copies"], 2)


def test_the_total_is_the_sum_of_the_parts():
    d = design()
    # exactly, not approximately: what is on screen has to add up
    assert d["yarn"]["mass_g"] == round(sum(p["yarn"]["mass_g_total"] for p in d["parts"]), 1)
    assert d["yarn"]["length_m"] == round(sum(p["yarn"]["length_m_total"] for p in d["parts"]), 2)


def test_no_two_differently_sized_parts_come_out_the_same_weight():
    d = design()
    by_name = {p["name"]: p for p in d["parts"]}
    # ordered by how much fabric each one is, smallest first
    order = ["Ear", "Arm", "Head", "Body"]
    masses = [by_name[n]["yarn"]["mass_g_each"] for n in order]
    assert masses == sorted(masses), masses
    assert len(set(masses)) == len(masses), masses


def test_weight_grows_with_the_finished_size():
    small = design(total_height_cm=12)["yarn"]["mass_g"]
    big = design(total_height_cm=24)["yarn"]["mass_g"]
    # twice as tall is roughly four times the surface, so well over double
    assert big > small * 3


def test_a_heavier_yarn_needs_more_grams_for_the_same_toy():
    dk = design(yarn_id="YARNSMITHS_DK")["yarn"]
    aran = design(yarn_id="YARNSMITHS_COTTONARAN")["yarn"]
    assert aran["mass_g"] > dk["mass_g"] * 1.2
    assert aran["g_per_m"] > dk["g_per_m"]


def test_a_part_with_no_known_tex_reports_length_only_rather_than_a_made_up_weight():
    d = design(yarn_id=None, yarn_diameter_mm=2.5)
    assert d["yarn"]["available"] is True
    assert d["yarn"]["mass_g"] is None and d["yarn"]["g_per_m"] is None
    assert all(p["yarn"]["mass_g_total"] is None for p in d["parts"])
    assert all(p["yarn"]["length_m_total"] > 0 for p in d["parts"])


def test_the_designer_and_the_single_piece_calculator_agree_on_the_same_piece():
    d = design()
    head = d["parts"][0]
    r = c.post("/api/complex-consumption/calculate", json={
        "program_type": "amigurumi",
        "program": {"initial_stitches": head["initial_stitches"], "rounds": head["rounds"]},
        "yarn_id": "YARNSMITHS_DK", "hook_mm": 3.0, "allowance_percent": 10,
        "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22, "domain_policy": "warn"})
    assert r.status_code == 200, r.text
    calc = r.json()["calculation"]
    assert calc["recommended_length_m"] == pytest.approx(head["yarn"]["length_m_each"], rel=0.005)
    assert calc["mass_g"] == pytest.approx(head["yarn"]["mass_g_each"], rel=0.02)
