import pytest
from fastapi.testclient import TestClient
import src.web.app as appmod

client = TestClient(appmod.app)


def _create_yarn(yarn_id, price_amount=None, package_mass_g=50, package_length_m=100):
    body = {
        "yarn_id": yarn_id, "brand": "Test", "product": "Line material",
        "package_mass_g": package_mass_g, "package_length_m": package_length_m,
        "fibre_composition": {"Acrylic": 100},
    }
    if price_amount is not None:
        body["price_amount"] = price_amount
        body["price_currency"] = "GBP"
    r = client.post("/api/yarns", json=body)
    assert r.status_code == 200, r.text
    return yarn_id


@pytest.fixture
def priced_yarn():
    yid = "PL_TEST_YARN_PRICED"
    _create_yarn(yid, price_amount=5.0, package_mass_g=50, package_length_m=100)
    yield yid
    client.delete(f"/api/admin/yarns/{yid}")


def test_create_list_update_delete_product_line():
    r = client.post("/api/admin/product-lines", json={
        "name": "PL Test Bear", "description": "A test bear.",
        "photo_url": "https://example.com/bear.jpg", "product_url": "https://example.com/product/bear",
    })
    assert r.status_code == 200, r.text
    line = r.json()
    assert line["name"] == "PL Test Bear"
    assert line["materials"] == []
    try:
        listed = client.get("/api/product-lines").json()
        assert any(l["id"] == line["id"] for l in listed)

        r2 = client.patch(f"/api/admin/product-lines/{line['id']}", json={"description": "Updated bear."})
        assert r2.status_code == 200, r2.text
        assert r2.json()["description"] == "Updated bear."
    finally:
        client.delete(f"/api/admin/product-lines/{line['id']}")
    assert client.delete(f"/api/admin/product-lines/{line['id']}").status_code == 404


def test_duplicate_name_is_rejected():
    r1 = client.post("/api/admin/product-lines", json={"name": "PL Dup Test"})
    assert r1.status_code == 200
    try:
        r2 = client.post("/api/admin/product-lines", json={"name": "PL Dup Test"})
        assert r2.status_code == 409
    finally:
        client.delete(f"/api/admin/product-lines/{r1.json()['id']}")


def test_add_material_computes_packages_and_cost(priced_yarn):
    line = client.post("/api/admin/product-lines", json={"name": "PL Materials Test"}).json()
    try:
        r = client.post(f"/api/admin/product-lines/{line['id']}/materials",
                         json={"yarn_id": priced_yarn, "length_m": 180})
        assert r.status_code == 200, r.text
        updated = r.json()
        mat = updated["materials"][0]
        # 180m needed / 100m per ball -> 2 balls, at 5.0 GBP each -> 10.0
        assert mat["packages"] == 2
        assert mat["cost"] == 10.0
        assert updated["total_cost"] == 10.0
        assert updated["total_cost_currency"] == "GBP"

        del_r = client.delete(f"/api/admin/product-lines/{line['id']}/materials/{mat['id']}")
        assert del_r.status_code == 200
        assert del_r.json()["materials"] == []
        assert del_r.json()["total_cost"] is None
    finally:
        client.delete(f"/api/admin/product-lines/{line['id']}")


def test_material_requires_length_or_weight(priced_yarn):
    line = client.post("/api/admin/product-lines", json={"name": "PL No Qty Test"}).json()
    try:
        r = client.post(f"/api/admin/product-lines/{line['id']}/materials", json={"yarn_id": priced_yarn})
        assert r.status_code == 422
    finally:
        client.delete(f"/api/admin/product-lines/{line['id']}")


def test_material_rejects_unknown_yarn():
    line = client.post("/api/admin/product-lines", json={"name": "PL Bad Yarn Test"}).json()
    try:
        r = client.post(f"/api/admin/product-lines/{line['id']}/materials",
                         json={"yarn_id": "DOES_NOT_EXIST", "length_m": 10})
        assert r.status_code == 422
    finally:
        client.delete(f"/api/admin/product-lines/{line['id']}")


def test_total_cost_omitted_when_a_material_has_no_price():
    unpriced = _create_yarn("PL_TEST_YARN_UNPRICED")
    line = client.post("/api/admin/product-lines", json={"name": "PL Partial Price Test"}).json()
    try:
        client.post(f"/api/admin/product-lines/{line['id']}/materials",
                    json={"yarn_id": unpriced, "length_m": 50})
        got = client.get("/api/product-lines").json()
        entry = next(l for l in got if l["id"] == line["id"])
        assert entry["materials"][0]["cost"] is None
        assert entry["total_cost"] is None
    finally:
        client.delete(f"/api/admin/product-lines/{line['id']}")
        client.delete(f"/api/admin/yarns/{unpriced}")


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    from src.web.auth import UserStore
    store = UserStore(tmp_path / "users.sqlite")
    monkeypatch.setattr(appmod, "user_store", store)
    store.create("plmarek", "correct-horse-1", role="admin")
    store.create("pluser", "another-pass-2", role="user")
    admin = TestClient(appmod.app)
    admin.post("/api/auth/login", json={"username": "plmarek", "password": "correct-horse-1"})
    user = TestClient(appmod.app)
    user.post("/api/auth/login", json={"username": "pluser", "password": "another-pass-2"})
    return admin, user


def test_non_admin_cannot_manage_product_lines(auth_client):
    admin, user = auth_client
    r = user.post("/api/admin/product-lines", json={"name": "PL Forbidden"})
    assert r.status_code == 403

    created = admin.post("/api/admin/product-lines", json={"name": "PL Read Only Test"})
    assert created.status_code == 200
    line_id = created.json()["id"]
    try:
        # any signed-in user can read the catalogue
        assert user.get("/api/product-lines").status_code == 200
    finally:
        admin.delete(f"/api/admin/product-lines/{line_id}")
