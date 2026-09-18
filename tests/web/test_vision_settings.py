import io
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

import src.web.app as appmod
from src.storage.backup import build_backup_zip

FAKE_KEY = "sk-ant-api03-thisisnotarealkey-000000000000"


@pytest.fixture
def admin_and_user(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from src.web.auth import UserStore
    store = UserStore(tmp_path / "users.sqlite")
    monkeypatch.setattr(appmod, "user_store", store)
    store.create("marek", "correct-horse-1", role="admin")
    store.create("eva", "another-pass-2", role="user")
    admin = TestClient(appmod.app)
    admin.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"})
    user = TestClient(appmod.app)
    user.post("/api/auth/login", json={"username": "eva", "password": "another-pass-2"})
    yield admin, user
    s = appmod.service._store()
    try:
        s.set_setting(appmod.VISION_KEY_SETTING, "")
        s.set_setting(appmod.VISION_MODEL_SETTING, "")
    finally:
        s.close()


def test_key_can_be_set_from_the_admin_page(admin_and_user):
    admin, _ = admin_and_user
    before = admin.get("/api/admin/settings/vision").json()
    assert before["configured"] is False and before["key_source"] is None

    r = admin.put("/api/admin/settings/vision", json={"api_key": FAKE_KEY})
    assert r.status_code == 200
    after = r.json()
    assert after["configured"] is True and after["key_source"] == "app"
    assert admin.get("/api/design/status").json()["vision_configured"] is True


def test_the_key_is_never_sent_back_to_a_browser(admin_and_user):
    admin, _ = admin_and_user
    admin.put("/api/admin/settings/vision", json={"api_key": FAKE_KEY})
    for body in (admin.get("/api/admin/settings/vision").text,
                 admin.get("/api/design/status").text,
                 admin.put("/api/admin/settings/vision", json={"model": "x"}).text):
        assert FAKE_KEY not in body
        assert FAKE_KEY[8:] not in body          # not even most of it
    hint = admin.get("/api/admin/settings/vision").json()["key_hint"]
    assert hint and hint.startswith("sk-ant-") and hint.endswith(FAKE_KEY[-4:])


def test_only_an_admin_can_see_or_set_it(admin_and_user):
    _, user = admin_and_user
    assert user.get("/api/admin/settings/vision").status_code == 403
    assert user.put("/api/admin/settings/vision", json={"api_key": FAKE_KEY}).status_code == 403


def test_obvious_nonsense_is_refused(admin_and_user):
    admin, _ = admin_and_user
    assert admin.put("/api/admin/settings/vision", json={"api_key": "short"}).status_code == 422
    assert admin.put("/api/admin/settings/vision",
                     json={"api_key": "key with spaces in it and long enough"}).status_code == 422


def test_clearing_falls_back_to_the_servers_own_key(admin_and_user, monkeypatch):
    admin, _ = admin_and_user
    admin.put("/api/admin/settings/vision", json={"api_key": FAKE_KEY})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env-key-0000000000000000")
    cleared = admin.put("/api/admin/settings/vision", json={"api_key": ""}).json()
    assert cleared["configured"] is True and cleared["key_source"] == "env"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert admin.get("/api/admin/settings/vision").json()["configured"] is False


def test_the_stored_key_is_the_one_used_for_photos(admin_and_user, monkeypatch):
    admin, _ = admin_and_user
    admin.put("/api/admin/settings/vision", json={"api_key": FAKE_KEY, "model": "test-model"})
    seen = {}

    def fake_describe(images, hint=None, timeout=60, api_key=None, model=None, _transport=None):
        seen["api_key"], seen["model"] = api_key, model
        return {"object": "ball", "confidence": "low", "parts": [
            {"name": "Ball", "category": "HEAD", "archetype": "sphere", "copies": 1,
             "height_fraction": 1.0, "width_fraction": 1.0}],
            "assembly": [], "uncertain": [], "dropped": [], "model": model}

    monkeypatch.setattr(appmod, "describe_photo", fake_describe)
    import base64
    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()
    r = admin.post("/api/design/from-photo", json={
        "total_height_cm": 10, "images": [{"media_type": "image/png", "data": png}]})
    assert r.status_code == 200, r.text
    assert seen["api_key"] == FAKE_KEY and seen["model"] == "test-model"


def test_the_key_is_stripped_from_downloaded_backups(tmp_path):
    # A backup gets emailed and kept for years; a spendable credential must not
    # travel with it.
    db = tmp_path / "web_app.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO settings VALUES (?,?)", ("secret.anthropic_api_key", FAKE_KEY))
    conn.execute("INSERT INTO settings VALUES (?,?)", ("company.company_name", "DesignLeaf"))
    conn.commit()
    conn.close()

    blob = build_backup_zip(tmp_path)
    assert FAKE_KEY.encode() not in blob

    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        out = tmp_path / "restored.sqlite"
        out.write_bytes(zf.read("web_app.sqlite"))
    rconn = sqlite3.connect(out)
    try:
        rows = dict(rconn.execute("SELECT key,value FROM settings").fetchall())
    finally:
        rconn.close()
    assert "secret.anthropic_api_key" not in rows      # dropped
    assert rows["company.company_name"] == "DesignLeaf"  # everything else survives
