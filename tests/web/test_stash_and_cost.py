from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)


def test_stash_upsert_list_delete():
    r = client.post("/api/stash", json={"yarn_id": "TEST_Y1", "quantity_g": 150, "notes": "3 skeins in the drawer"})
    assert r.status_code == 200, r.text
    assert r.json()["quantity_g"] == 150

    # upsert again updates the same row rather than creating a second one
    r2 = client.post("/api/stash", json={"yarn_id": "TEST_Y1", "quantity_g": 90})
    assert r2.status_code == 200
    listed = client.get("/api/stash").json()
    assert len([e for e in listed if e["yarn_id"] == "TEST_Y1"]) == 1
    assert listed[0]["quantity_g"] == 90

    assert client.delete("/api/stash/TEST_Y1").status_code == 200
    assert client.delete("/api/stash/TEST_Y1").status_code == 404


def test_stash_requires_a_quantity():
    r = client.post("/api/stash", json={"yarn_id": "TEST_Y1"})
    assert r.status_code == 422


def test_stash_unknown_yarn_404():
    r = client.post("/api/stash", json={"yarn_id": "NO_SUCH_YARN", "quantity_g": 50})
    assert r.status_code == 404


def _priced_yarn(yarn_id="COST_TEST_YARN"):
    return client.post("/api/yarns", json={
        "yarn_id": yarn_id, "brand": "Test", "product": "Priced",
        "package_mass_g": 50, "package_length_m": 100, "fibre_composition": {"Acrylic": 100},
        "price_amount": 4.0, "price_currency": "GBP",
    })


def _calc_body(yarn_id):
    return {
        "pattern_id": "RIB_2X2", "pattern_version": "1.0.0", "yarn_id": yarn_id,
        "width_cm": 50, "height_cm": 60, "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 28,
        "allowance_percent": 8, "partial_repeat_mode": "reject",
        "edges": {"left_stitches": 2, "right_stitches": 2, "left_operation": "K", "right_operation": "K"},
        "calculation_mode": "swatch", "swatch": {"stitches": 40, "rows": 56, "yarn_length_m": 15},
    }


def test_calculate_includes_cost_estimate_when_yarn_has_a_price():
    _priced_yarn()
    try:
        d = client.post("/api/calculate", json=_calc_body("COST_TEST_YARN")).json()
        packages = d["consumption"]["packages"]
        assert d["cost_estimate"] is not None
        assert d["cost_estimate"]["packages"] == packages
        assert d["cost_estimate"]["amount"] == round(4.0 * packages, 2)
        assert d["cost_estimate"]["currency"] == "GBP"
    finally:
        client.delete("/api/admin/yarns/COST_TEST_YARN")


def test_calculate_cost_estimate_is_none_without_a_price():
    d = client.post("/api/calculate", json=_calc_body("TEST_Y1")).json()
    assert d["cost_estimate"] is None
