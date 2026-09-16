from fastapi.testclient import TestClient
from src.web.app import app
from src.web.bootstrap import ensure_demo_database

client = TestClient(app)


def _create_yarn(yarn_id="ENRICH_TEST_YARN"):
    return client.post("/api/yarns", json={
        "yarn_id": yarn_id, "brand": "Test", "product": "Enrichable",
        "package_mass_g": 50, "package_length_m": 100, "fibre_composition": {"Acrylic": 100},
        "description": "A soft test yarn.", "photo_url": "https://example.com/photo.jpg",
        "product_line": "Test Line", "price_amount": 3.5, "price_currency": "GBP",
    })


def test_create_yarn_with_enrichment_fields():
    r = _create_yarn()
    assert r.status_code == 200, r.text
    y = r.json()["yarn"]
    assert y["description"] == "A soft test yarn."
    assert y["photo_url"] == "https://example.com/photo.jpg"
    assert y["product_line"] == "Test Line"
    assert y["price_amount"] == 3.5 and y["price_currency"] == "GBP"
    client.delete("/api/admin/yarns/ENRICH_TEST_YARN")


def test_patch_yarn_updates_only_collaborative_fields():
    _create_yarn("ENRICH_PATCH_YARN")
    try:
        r = client.patch("/api/yarns/ENRICH_PATCH_YARN", json={"price_amount": 4.25, "description": "Updated."})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["price_amount"] == 4.25 and d["description"] == "Updated."
        # structural fields (brand, package_mass_g) are untouched by the patch endpoint
        assert d["brand"] == "Test" and d["package_mass_g"] == 50
    finally:
        client.delete("/api/admin/yarns/ENRICH_PATCH_YARN")


def test_patch_unknown_yarn_404():
    r = client.patch("/api/yarns/NO_SUCH_YARN", json={"price_amount": 1.0})
    assert r.status_code == 404


def test_patch_requires_at_least_one_field():
    _create_yarn("ENRICH_EMPTY_PATCH")
    try:
        r = client.patch("/api/yarns/ENRICH_EMPTY_PATCH", json={})
        assert r.status_code == 422
    finally:
        client.delete("/api/admin/yarns/ENRICH_EMPTY_PATCH")


def test_supplier_crud_and_ordering_by_price():
    _create_yarn("ENRICH_SUPPLIER_YARN")
    try:
        a = client.post("/api/yarns/ENRICH_SUPPLIER_YARN/suppliers", json={
            "name": "Pricier Shop", "price_amount": 9.0, "price_currency": "GBP",
            "product_url": "https://shop-a.example/yarn"})
        b = client.post("/api/yarns/ENRICH_SUPPLIER_YARN/suppliers", json={
            "name": "Cheaper Shop", "price_amount": 3.0, "price_currency": "GBP",
            "product_url": "https://shop-b.example/yarn"})
        assert a.status_code == 200 and b.status_code == 200

        listed = client.get("/api/yarns/ENRICH_SUPPLIER_YARN/suppliers").json()
        assert [s["name"] for s in listed] == ["Cheaper Shop", "Pricier Shop"]

        sid = listed[0]["id"]
        assert client.delete(f"/api/admin/yarns/ENRICH_SUPPLIER_YARN/suppliers/{sid}").status_code == 200
        assert client.delete(f"/api/admin/yarns/ENRICH_SUPPLIER_YARN/suppliers/{sid}").status_code == 404
        remaining = client.get("/api/yarns/ENRICH_SUPPLIER_YARN/suppliers").json()
        assert len(remaining) == 1 and remaining[0]["name"] == "Pricier Shop"
    finally:
        client.delete("/api/admin/yarns/ENRICH_SUPPLIER_YARN")


def test_supplier_on_unknown_yarn_404():
    r = client.post("/api/yarns/NO_SUCH_YARN/suppliers", json={"name": "X"})
    assert r.status_code == 404


def test_reimporting_bundled_fixtures_does_not_clobber_admin_edits(tmp_path):
    """ensure_demo_database re-synchronizes the bundled yarn library on every
    startup. A price/description an admin has set on a bundled yarn must
    survive that re-sync, or every deploy would silently wipe it (M13)."""
    r = client.patch("/api/yarns/DROPS_SAFRAN_50G_160M", json={"price_amount": 2.75, "price_currency": "GBP"})
    assert r.status_code == 200
    from src.web.app import ROOT, DB_PATH
    ensure_demo_database(ROOT, DB_PATH)
    y = next(y for y in client.get("/api/yarns").json() if y["yarn_id"] == "DROPS_SAFRAN_50G_160M")
    assert y["price_amount"] == 2.75
