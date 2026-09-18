"""The Yarnsmiths range, as read from the brand's own product pages.

These guard the import rather than the website: every record must be complete,
arithmetically consistent with what the page stated, and usable by the
calculator. If a future re-import silently mangles a blend or a ball size,
these fail.
"""
import json
from pathlib import Path

import pytest

from src.library.yarn import YarnRecord

ROOT = Path(__file__).resolve().parents[2]
RECORDS = sorted((ROOT / "data/yarns").glob("YARNSMITHS_*.json"))
CAPTURE = json.loads((ROOT / "data/ingestion/yarnsmiths_capture_2026-09-18.json").read_text())


def load(p):
    d = json.loads(p.read_text())
    d.pop("record_type", None)
    return d


def test_the_whole_range_is_present():
    assert len(RECORDS) == 53
    assert len(CAPTURE) == 53


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.stem)
def test_each_record_is_valid_and_complete(path):
    d = load(path)
    YarnRecord(**d)                      # raises if anything is out of range
    assert d["brand"] == "Yarnsmiths"
    assert d["product"]
    assert d["package_mass_g"] > 0 and d["package_length_m"] > 0
    assert 0 <= d["cyc_weight"] <= 7
    assert d["recommended_needle_min_mm"] and d["recommended_needle_max_mm"]
    assert d["source_reference"].startswith("https://www.woolwarehouse.co.uk/yarn/yarnsmiths-")
    assert abs(sum(d["fibre_composition"].values()) - 100) < 0.05


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.stem)
def test_tex_is_derived_from_the_stated_ball_not_guessed(path):
    d = load(path)
    assert abs(d["tex"] - d["package_mass_g"] / d["package_length_m"] * 1000) < 1e-6


def test_figures_match_the_captured_pages():
    by_url = {json.loads(p.read_text())["source_reference"]: json.loads(p.read_text())
              for p in RECORDS}
    for entry in CAPTURE:
        rec = by_url["https://www.woolwarehouse.co.uk" + entry["s"]]
        assert rec["product"] == entry["Yarn Name"]
        assert str(int(rec["package_mass_g"])) + "g" == entry["Ball Weight"].strip()
        assert str(int(rec["package_length_m"])) in entry["Length"]


def test_known_products_came_out_right():
    # The yarn from the invoice that started this, and a jumbo one where the
    # shop's own "super chunky" label understates the CYC standard weight.
    cotton_aran = load(ROOT / "data/yarns/YARNSMITHS_COTTONARAN.json")
    assert (cotton_aran["package_mass_g"], cotton_aran["package_length_m"]) == (50.0, 80.0)
    assert cotton_aran["fibre_composition"] == {"Cotton": 100.0}
    assert cotton_aran["cyc_weight"] == 4                  # aran
    assert cotton_aran["recommended_needle_min_mm"] == 5.0

    tweed = load(ROOT / "data/yarns/YARNSMITHS_MERINOARANTWEED.json")
    assert tweed["fibre_composition"] == {"Viscose": 3.0, "Wool": 97.0}   # "3% Viscose97% Wool"

    jumbo = load(ROOT / "data/yarns/YARNSMITHS_SNUGRRB300.json")
    assert jumbo["recommended_needle_max_mm"] == 30.0
    assert jumbo["cyc_weight"] == 7                        # 30 mm needles is jumbo, not super chunky


def test_no_duplicate_ids_across_the_whole_library():
    ids = [json.loads(p.read_text())["yarn_id"] for p in (ROOT / "data/yarns").glob("*.json")]
    assert len(ids) == len(set(ids))
