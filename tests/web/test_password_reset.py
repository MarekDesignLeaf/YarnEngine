import pytest
from fastapi.testclient import TestClient
import src.web.app as appmod
from src.web.auth import UserStore


@pytest.fixture
def auth_client(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    store = UserStore(tmp_path / "users.sqlite")
    monkeypatch.setattr(appmod, "user_store", store)
    appmod._reset_attempts.clear()
    return TestClient(appmod.app), store


def test_forgot_password_issues_a_working_reset_token(auth_client, monkeypatch):
    c, store = auth_client
    u = store.create("marek", "old-password-1", role="admin", email="marek@designleaf.co.uk")

    sent = {}
    def fake_send_email(to, subject, html, text=None):
        sent["to"] = to
        sent["html"] = html
        return True
    monkeypatch.setattr(appmod, "send_email", fake_send_email)

    r = c.post("/api/auth/forgot-password", json={"username_or_email": "marek"})
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    assert sent["to"] == "marek@designleaf.co.uk"
    assert "reset_token=" in sent["html"]

    token = sent["html"].split("reset_token=")[1].split('"')[0]
    reset = c.post("/api/auth/reset-password", json={"token": token, "new_password": "new-password-2"})
    assert reset.status_code == 200 and reset.json()["username"] == "marek"
    # signed in immediately after a successful reset
    assert c.get("/api/auth/me").json()["username"] == "marek"

    # old password no longer works, new one does
    c2 = TestClient(appmod.app)
    assert c2.post("/api/auth/login", json={"username": "marek", "password": "old-password-1"}).status_code == 401
    assert c2.post("/api/auth/login", json={"username": "marek", "password": "new-password-2"}).status_code == 200

    # the token is single-use
    c3 = TestClient(appmod.app)
    reuse = c3.post("/api/auth/reset-password", json={"token": token, "new_password": "another-pass-3"})
    assert reuse.status_code == 400


def test_forgot_password_by_email_and_unknown_identifier(auth_client, monkeypatch):
    c, store = auth_client
    store.create("eva", "correct-horse-1", email="eva@example.com")
    monkeypatch.setattr(appmod, "send_email", lambda *a, **k: True)

    assert c.post("/api/auth/forgot-password", json={"username_or_email": "eva@example.com"}).status_code == 200
    # unknown identifier still returns a generic ok (no user enumeration)
    assert c.post("/api/auth/forgot-password", json={"username_or_email": "nobody-here"}).status_code == 200
    # user with no email on file: still ok, nothing sent (can't assert silently-not-sent directly,
    # but it must not error)
    store.create("noemail", "correct-horse-2")
    assert c.post("/api/auth/forgot-password", json={"username_or_email": "noemail"}).status_code == 200


def test_reset_password_rejects_invalid_or_expired_token(auth_client):
    c, store = auth_client
    assert c.post("/api/auth/reset-password", json={"token": "not-a-real-token", "new_password": "whatever12"}).status_code == 400

    u = store.create("marek", "old-password-1", email="marek@designleaf.co.uk")
    token = store.create_password_reset(u["id"])
    # too-short new password is rejected with 422, not 400 (token itself is valid)
    assert c.post("/api/auth/reset-password", json={"token": token, "new_password": "short"}).status_code == 422


def test_forgot_password_is_rate_limited(auth_client, monkeypatch):
    c, store = auth_client
    store.create("marek", "correct-horse-1", email="marek@designleaf.co.uk")
    monkeypatch.setattr(appmod, "send_email", lambda *a, **k: True)
    for _ in range(appmod.RESET_MAX_ATTEMPTS):
        assert c.post("/api/auth/forgot-password", json={"username_or_email": "marek"}).status_code == 200
    limited = c.post("/api/auth/forgot-password", json={"username_or_email": "marek"})
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_self_service_and_admin_email_management(auth_client):
    c, store = auth_client
    store.create("marek", "correct-horse-1", role="admin")
    c.post("/api/auth/login", json={"username": "marek", "password": "correct-horse-1"})

    r = c.put("/api/auth/email", json={"email": "marek@designleaf.co.uk"})
    assert r.status_code == 200 and r.json()["email"] == "marek@designleaf.co.uk"
    assert c.get("/api/auth/me").json()["email"] == "marek@designleaf.co.uk"

    bad = c.put("/api/auth/email", json={"email": "not-an-email"})
    assert bad.status_code == 422

    created = c.post("/api/admin/users", json={"username": "sarah", "password": "correct-horse-2", "email": "sarah@example.com"})
    assert created.status_code == 200 and created.json()["email"] == "sarah@example.com"

    updated = c.put(f"/api/admin/users/{created.json()['id']}", json={"email": "sarah2@example.com"})
    assert updated.status_code == 200 and updated.json()["email"] == "sarah2@example.com"
