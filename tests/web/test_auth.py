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

def test_yarn_delete_is_admin_only(auth_client):
    c, store = auth_client
    store.create("marek", "correct-horse-1", role="admin")
    store.create("eva", "another-pass-2", role="user")
    admin = TestClient(appmod.app)
    admin.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"})
    user = TestClient(appmod.app)
    user.post("/api/auth/login", json={"username": "eva", "password": "another-pass-2"})

    created = admin.post("/api/yarns", json={
        "yarn_id": "DELETE_ME_TEST_YARN", "brand": "Test", "product": "Deletable",
        "package_mass_g": 50, "package_length_m": 100, "fibre_composition": {"Acrylic": 100},
    })
    assert created.status_code == 200

    assert user.delete("/api/admin/yarns/DELETE_ME_TEST_YARN").status_code == 403
    assert admin.delete("/api/admin/yarns/DELETE_ME_TEST_YARN").status_code == 200
    assert admin.delete("/api/admin/yarns/DELETE_ME_TEST_YARN").status_code == 404
    assert not any(y["yarn_id"] == "DELETE_ME_TEST_YARN" for y in admin.get("/api/yarns").json())


def test_swatch_and_calibration_delete_are_admin_only(auth_client, monkeypatch, tmp_path):
    c, store = auth_client
    store.create("marek", "correct-horse-1", role="admin")
    store.create("eva", "another-pass-2", role="user")
    admin = TestClient(appmod.app)
    admin.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"})
    user = TestClient(appmod.app)
    user.post("/api/auth/login", json={"username": "eva", "password": "another-pass-2"})

    yarn = admin.post("/api/yarns", json={
        "yarn_id": "ADMIN_ONLY_DELETE_TEST_YARN", "brand": "Test", "product": "Deletable",
        "package_mass_g": 50, "package_length_m": 100, "fibre_composition": {"Acrylic": 100},
    })
    assert yarn.status_code in (200, 409)
    swatch = admin.post("/api/swatches", json={
        "name": "Admin-only delete test", "pattern_id": "STOCKINETTE", "pattern_version": "1.0.0",
        "yarn_id": "ADMIN_ONLY_DELETE_TEST_YARN", "needle_mm": 4, "stitches": 20, "rows": 28,
        "width_cm": 10, "height_cm": 10, "yarn_length_m": 8,
    })
    assert swatch.status_code == 200
    sid = swatch.json()["swatch_id"]
    assert user.delete(f"/api/swatches/{sid}").status_code == 403
    assert admin.delete(f"/api/swatches/{sid}").status_code == 200

    from src.crochet_calibration.store import CrochetCalibrationStore
    cal_store = CrochetCalibrationStore(tmp_path / "cal_test.sqlite")
    monkeypatch.setattr(appmod, "crochet_cal_store", cal_store)
    rec = {"record_id": "admin_only_r1", "replicate_group_id": "g", "crocheter_id": "c", "yarn_id": "y",
           "hook_mm": 3, "gauge_stitches": 20, "gauge_rows": 20, "gauge_width_mm": 100, "gauge_height_mm": 100,
           "operation_counts": {"SC": 400}, "yarn_length_m": 10}
    assert admin.post("/api/crochet/calibration/records", json=rec).status_code == 200
    assert user.delete("/api/crochet/calibration/records/admin_only_r1").status_code == 403
    assert admin.delete("/api/crochet/calibration/records/admin_only_r1").status_code == 200
    cal_store.close()


def test_login_is_rate_limited_after_repeated_failures(auth_client):
    c, store = auth_client
    store.create("marek", "correct-horse-1", role="admin")
    appmod._login_attempts.clear()
    for _ in range(appmod.LOGIN_MAX_ATTEMPTS):
        r = c.post("/api/auth/login", json={"username": "marek", "password": "wrong"})
        assert r.status_code == 401
    limited = c.post("/api/auth/login", json={"username": "marek", "password": "wrong"})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers
    # correct password is blocked too while the window is active
    assert c.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"}).status_code == 429
    appmod._login_attempts.clear()


def test_admin_backup_download(auth_client):
    c, store = auth_client
    store.create("marek", "correct-horse-1", role="admin")
    store.create("eva", "another-pass-2", role="user")
    admin = TestClient(appmod.app)
    admin.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"})
    user = TestClient(appmod.app)
    user.post("/api/auth/login", json={"username": "eva", "password": "another-pass-2"})

    assert user.get("/api/admin/backup").status_code == 403
    r = admin.get("/api/admin/backup")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    import io, zipfile
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert any(n.endswith("users.sqlite") for n in zf.namelist())


def test_seed_admin_from_env(tmp_path, monkeypatch):
    from src.web.auth import UserStore
    monkeypatch.setenv("ADMIN_USERNAME", "marek")
    monkeypatch.setenv("ADMIN_PASSWORD", "seeded-pass-9")
    store = UserStore(tmp_path / "u.sqlite")
    seeded = store.seed_admin_from_env()
    assert seeded["role"] == "admin"
    assert store.authenticate("marek", "seeded-pass-9")
    assert store.seed_admin_from_env() is None  # only when empty
