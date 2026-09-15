import os
import pytest
from fastapi.testclient import TestClient
import src.web.app as appmod

@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    # isolate users for this test
    from src.web.auth import UserStore
    store = UserStore(tmp_path / "users.sqlite")
    monkeypatch.setattr(appmod, "user_store", store)
    return TestClient(appmod.app), store

def test_api_requires_login_when_auth_enabled(auth_client):
    c, _ = auth_client
    assert c.get("/api/health").status_code == 200          # public
    assert c.get("/").status_code == 200                    # login page is public
    assert c.get("/api/patterns").status_code == 401        # protected

def test_first_registration_becomes_admin_and_grants_session(auth_client):
    c, store = auth_client
    r = c.post("/api/auth/register", json={"username": "marek", "password": "correct-horse-1"})
    assert r.status_code == 200 and r.json()["role"] == "admin"
    assert c.get("/api/auth/me").json()["username"] == "marek"
    assert c.get("/api/patterns").status_code == 200
    assert c.get("/api/admin/users").status_code == 200
    # second registration is a plain user without admin rights
    c2 = TestClient(appmod.app)
    r2 = c2.post("/api/auth/register", json={"username": "eva", "password": "another-pass-2"})
    assert r2.json()["role"] == "user"
    assert c2.get("/api/admin/users").status_code == 403

def test_login_rejects_bad_password_and_inactive_user(auth_client):
    c, store = auth_client
    store.create("marek", "correct-horse-1", role="admin")
    assert c.post("/api/auth/login", json={"username": "marek", "password": "wrong"}).status_code == 401
    ok = c.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"})
    assert ok.status_code == 200
    u = store.create("eva", "another-pass-2")
    store.set_active(u["id"], False)
    c3 = TestClient(appmod.app)
    assert c3.post("/api/auth/login", json={"username": "eva", "password": "another-pass-2"}).status_code == 401

def test_admin_cannot_lock_self_out(auth_client):
    c, store = auth_client
    me = store.create("marek", "correct-horse-1", role="admin")
    c.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"})
    assert c.put(f"/api/admin/users/{me['id']}", json={"active": False}).status_code == 422
    assert c.delete(f"/api/admin/users/{me['id']}").status_code == 422

def test_seed_admin_from_env(tmp_path, monkeypatch):
    from src.web.auth import UserStore
    monkeypatch.setenv("ADMIN_USERNAME", "marek")
    monkeypatch.setenv("ADMIN_PASSWORD", "seeded-pass-9")
    store = UserStore(tmp_path / "u.sqlite")
    seeded = store.seed_admin_from_env()
    assert seeded["role"] == "admin"
    assert store.authenticate("marek", "seeded-pass-9")
    assert store.seed_admin_from_env() is None  # only when empty
