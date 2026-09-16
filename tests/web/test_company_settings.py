import pytest
from fastapi.testclient import TestClient
import src.web.app as appmod


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    from src.web.auth import UserStore
    store = UserStore(tmp_path / "users.sqlite")
    monkeypatch.setattr(appmod, "user_store", store)
    store.create("marek", "correct-horse-1", role="admin")
    store.create("eva", "another-pass-2", role="user")
    admin = TestClient(appmod.app)
    admin.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"})
    user = TestClient(appmod.app)
    user.post("/api/auth/login", json={"username": "eva", "password": "another-pass-2"})
    return admin, user


def test_company_settings_round_trip_shape(auth_client):
    """Company settings are a global singleton (not per-test-isolated like the
    user/project stores), so this clears every field via the API itself first
    rather than assuming a pristine starting state left by other tests."""
    admin, _ = auth_client
    empty = {"company_name": "", "address": "", "ico": "", "dic": "", "email": "", "phone": "", "website": ""}
    cleared = admin.put("/api/admin/settings/company", json=empty).json()
    assert cleared == empty
    assert admin.get("/api/settings/company").json() == empty


def test_admin_can_set_company_settings_and_anyone_can_read_them(auth_client):
    admin, user = auth_client
    r = admin.put("/api/admin/settings/company", json={
        "company_name": "PiLoop s.r.o.", "email": "hello@piloop.example", "website": "https://piloop.example"})
    assert r.status_code == 200
    assert r.json()["company_name"] == "PiLoop s.r.o."

    d = user.get("/api/settings/company").json()
    assert d["company_name"] == "PiLoop s.r.o."
    assert d["email"] == "hello@piloop.example"


def test_non_admin_cannot_edit_company_settings(auth_client):
    _, user = auth_client
    r = user.put("/api/admin/settings/company", json={"company_name": "Hijacked"})
    assert r.status_code == 403
