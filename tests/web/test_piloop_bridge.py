"""Safety and integration checks for the PILOOP owner SSO and account-management bridge."""
import json
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.web.piloop_bridge import PiloopBridge

SECRET = "bridge-test-secret-64-byte-equivalent-for-local-testing-only"


def test_signed_owner_assertion_is_one_time_short_lived_and_not_a_password(tmp_path: Path):
    clock = [1700000000]
    issuer = PiloopBridge(SECRET, tmp_path / "issuer.db", lambda: clock[0])
    consumer = PiloopBridge(SECRET, tmp_path / "consumer.db", lambda: clock[0])
    assertion = issuer.mint_owner_assertion()
    assert SECRET not in assertion and "password" not in assertion
    assert consumer.redeem_owner_assertion(assertion)["sub"] == "owner"
    with pytest.raises(ValueError, match="reused"):
        consumer.redeem_owner_assertion(assertion)
    # Redeeming through another instance sharing the same persistent database is blocked.
    another = PiloopBridge(SECRET, tmp_path / "consumer.db", lambda: clock[0])
    with pytest.raises(ValueError, match="reused"):
        another.redeem_owner_assertion(assertion)
    clock[0] += 65
    with pytest.raises(ValueError):
        consumer.redeem_owner_assertion(issuer.mint_owner_assertion().replace("v1.", "v2.", 1))
    stale = issuer.mint_owner_assertion()
    clock[0] += 61
    with pytest.raises(ValueError):
        consumer.redeem_owner_assertion(stale)
    for bridge in (issuer, consumer, another):
        bridge.close()


def test_bridge_api_signature_rejects_replay_modified_body_and_expired_request(tmp_path: Path):
    clock = [1700000000]
    signer = PiloopBridge(SECRET, tmp_path / "signer.db", lambda: clock[0])
    verifier = PiloopBridge(SECRET, tmp_path / "verifier.db", lambda: clock[0])
    body = json.dumps({"action": "list"}).encode()
    headers = signer.sign_api("POST", "/api/piloop-bridge/v1", body)
    normalized = {k.lower(): v for k, v in headers.items()}
    verifier.verify_api("POST", "/api/piloop-bridge/v1", body, normalized)
    with pytest.raises(ValueError):
        verifier.verify_api("POST", "/api/piloop-bridge/v1", body, normalized)
    fresh = {k.lower(): v for k, v in signer.sign_api("POST", "/api/piloop-bridge/v1", body).items()}
    with pytest.raises(ValueError):
        verifier.verify_api("POST", "/api/piloop-bridge/v1", b'{"action":"create"}', fresh)
    clock[0] += 90
    with pytest.raises(ValueError):
        verifier.verify_api("POST", "/api/piloop-bridge/v1", body, fresh)
    signer.close()
    verifier.close()


def test_owner_sso_and_management_reuse_yarn_user_store(tmp_path, monkeypatch):
    from src.web import app as appmod
    from src.web.auth import UserStore
    store = UserStore(tmp_path / "users.db")
    owner = store.create("owner_local", "owner-pass-1234", role="admin")
    normal = store.create("normal_local", "normal-pass-1234", role="user")
    old_bridge = appmod.piloop_bridge
    test_bridge = PiloopBridge(SECRET, tmp_path / "bridge.db")
    issuer = PiloopBridge(SECRET, tmp_path / "issuer.db")
    monkeypatch.setattr(appmod, "piloop_bridge", test_bridge)
    monkeypatch.setattr(appmod, "user_store", store)
    monkeypatch.setenv("PILOOP_SSO_ADMIN_USERNAME", "owner_local")
    monkeypatch.delenv("YARNENGINE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    client = TestClient(appmod.app)
    try:
        # Wrong origin and anonymous access cannot bypass the application.
        token = issuer.mint_owner_assertion()
        assert client.post("/api/auth/piloop-sso", data={"assertion": token},
                           headers={"Origin": "https://not-piloop.example"},
                           follow_redirects=False).status_code == 403
        assert client.get("/api/admin/users").status_code == 401
        ok = client.post("/api/auth/piloop-sso", data={"assertion": token},
                         headers={"Origin": "https://piloop.co.uk"},
                         follow_redirects=False)
        assert ok.status_code == 303
        assert "ye_session=" in ok.headers.get("set-cookie", "")
        me = client.get("/api/auth/me").json()
        assert me["username"] == "owner_local" and me["role"] == "admin"
        # User administration is now served by PILOOP, not the local admin routes.
        assert client.get("/api/admin/users").status_code == 403
        assert client.post("/api/auth/piloop-sso", data={"assertion": token},
                           headers={"Origin": "https://piloop.co.uk"},
                           follow_redirects=False).status_code == 401
        def bridge_call(payload, *, sign=True):
            body = json.dumps(payload).encode()
            headers = {"Content-Type": "application/json"}
            if sign:
                headers.update(issuer.sign_api("POST", "/api/piloop-bridge/v1", body))
            return client.post("/api/piloop-bridge/v1", content=body, headers=headers)
        assert bridge_call({"action":"list"}, sign=False).status_code == 403
        result = bridge_call({"action": "list"})
        assert result.status_code == 200
        assert any(u["linked_owner"] for u in result.json()["users"])
        assert bridge_call({"action":"update", "user_id":owner["id"],"role":"user"}).status_code == 422
        created = bridge_call({"action":"create","username":"guest_bridge",
                               "password":"bridge-long-pass-12345","role":"user"})
        assert created.status_code == 200
        guest_id = created.json()["user"]["id"]
        role_result = bridge_call({"action":"catalogue_roles","user_id":guest_id,
                                   "roles":["HUMAN_REVIEWER"]})
        assert role_result.status_code == 200
        assert store.catalogue_roles(guest_id) == ["HUMAN_REVIEWER"]
        # Existing admin has all catalogue permissions even when explicit catalogue RBAC is in use.
        assert store.catalogue_role_assignment_count() > 0
        req = type("R", (), {"state": type("S", (), {"user":store.public(store.get(owner["id"]))})()})()
        appmod._require_catalogue_role(req, "LEGAL_AUTHORITY")
        req.state.user = store.public(store.get(normal["id"]))
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as denied:
            appmod._require_catalogue_role(req, "LEGAL_AUTHORITY")
        assert denied.value.status_code == 403
    finally:
        monkeypatch.setattr(appmod, "piloop_bridge", old_bridge)
        client.close()
        test_bridge.close()
        issuer.close()
        store.conn.close()


def test_nonce_replay_survives_restart(tmp_path):
    clock = [1700000000]
    signer = PiloopBridge(SECRET, tmp_path / "signer.db", lambda: clock[0])
    first = PiloopBridge(SECRET, tmp_path / "verifier.db", lambda: clock[0])
    body = b'{"action":"list"}'
    headers = {k.lower(): v for k, v in signer.sign_api("POST", "/api/piloop-bridge/v1", body).items()}
    first.verify_api("POST", "/api/piloop-bridge/v1", body, headers)
    token = signer.mint_owner_assertion()
    first.redeem_owner_assertion(token)
    first.close()
    restarted = PiloopBridge(SECRET, tmp_path / "verifier.db", lambda: clock[0])
    with pytest.raises(ValueError):
        restarted.verify_api("POST", "/api/piloop-bridge/v1", body, headers)
    with pytest.raises(ValueError):
        restarted.redeem_owner_assertion(token)
    wrong_key = PiloopBridge("x" * 40, tmp_path / "wrong.db", lambda: clock[0])
    with pytest.raises(ValueError):
        restarted.redeem_owner_assertion(wrong_key.mint_owner_assertion())
    for b in (signer, restarted, wrong_key):
        b.close()


def test_invalid_bridge_secret_disables_bridge_without_stopping_app(monkeypatch):
    from src.web import app as appmod
    monkeypatch.setenv("PILOOP_BRIDGE_SECRET", "too-short")
    assert appmod._start_piloop_bridge() is None
    monkeypatch.delenv("PILOOP_BRIDGE_SECRET")
    assert appmod._start_piloop_bridge() is None


def test_linked_owner_is_protected_and_keeps_catalogue_authority_without_bridge(tmp_path, monkeypatch):
    from src.web import app as appmod
    from src.web.auth import UserStore
    from fastapi import HTTPException
    store = UserStore(tmp_path / "users.db")
    owner = store.create("owner_local", "owner-pass-1234", role="admin")
    second = store.create("second_admin", "second-pass-1234", role="admin")
    reviewer = store.create("reviewer", "reviewer-pass-1234", role="user")
    store.set_catalogue_roles(reviewer["id"], ["HUMAN_REVIEWER"])  # explicit RBAC is now active
    monkeypatch.setattr(appmod, "user_store", store)
    monkeypatch.setattr(appmod, "piloop_bridge", None)  # bridge unavailable: recovery by direct login
    monkeypatch.setenv("PILOOP_SSO_ADMIN_USERNAME", "owner_local")
    monkeypatch.delenv("YARNENGINE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    req = type("R", (), {"state": type("S", (), {"user": store.public(store.get(owner["id"]))})()})()
    for role in ("OPERATOR", "HUMAN_REVIEWER", "CR_AUTHORITY", "RELEASE_AUTHORITY", "LEGAL_AUTHORITY"):
        appmod._require_catalogue_role(req, role)
    req.state.user = store.public(store.get(second["id"]))
    with pytest.raises(HTTPException):
        appmod._require_catalogue_role(req, "LEGAL_AUTHORITY")
    client = TestClient(appmod.app)
    try:
        assert client.post("/api/auth/login", json={"username": "second_admin",
                                                    "password": "second-pass-1234"}).status_code == 200
        oid = owner["id"]
        assert client.put(f"/api/admin/users/{oid}", json={"role": "user"}).status_code == 422
        assert client.put(f"/api/admin/users/{oid}", json={"active": False}).status_code == 422
        assert client.delete(f"/api/admin/users/{oid}").status_code == 422
        refreshed = store.get(oid)
        assert refreshed["role"] == "admin" and refreshed["active"]
        # Other accounts remain manageable.
        assert client.put(f"/api/admin/users/{reviewer['id']}", json={"active": False}).status_code == 200
        # Without the bridge, SSO and bridge endpoints are unavailable but ordinary login works.
        assert client.post("/api/auth/piloop-sso", data={"assertion": "v1.x.y"},
                           headers={"Origin": "https://piloop.co.uk"}).status_code == 503
        assert client.post("/api/piloop-bridge/v1", content=b"{}").status_code == 503
    finally:
        client.close()
        store.conn.close()


def test_ordinary_user_cannot_mint_forge_or_reuse_owner_sso(tmp_path, monkeypatch):
    from src.web import app as appmod
    from src.web.auth import UserStore
    store = UserStore(tmp_path / "users.db")
    store.create("owner_local", "owner-pass-1234", role="admin")
    store.create("guest_user", "guest-pass-12345", role="user")
    bridge = PiloopBridge(SECRET, tmp_path / "bridge.db")
    forger = PiloopBridge("guessed-secret-guessed-secret-guessed-secret", tmp_path / "f.db")
    monkeypatch.setattr(appmod, "user_store", store)
    monkeypatch.setattr(appmod, "piloop_bridge", bridge)
    monkeypatch.setenv("PILOOP_SSO_ADMIN_USERNAME", "owner_local")
    monkeypatch.delenv("YARNENGINE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    client = TestClient(appmod.app)
    try:
        assert client.post("/api/auth/login", json={"username": "guest_user",
                                                    "password": "guest-pass-12345"}).status_code == 200
        assert client.get("/api/admin/users").status_code == 403
        origin = {"Origin": "https://piloop.co.uk"}
        assert client.post("/api/auth/piloop-sso", data={"assertion": forger.mint_owner_assertion()},
                           headers=origin, follow_redirects=False).status_code == 401
        tampered = bridge.mint_owner_assertion()
        head, payload, sig = tampered.split(".")
        assert client.post("/api/auth/piloop-sso", data={"assertion": head + "." + payload + "A." + sig},
                           headers=origin, follow_redirects=False).status_code == 401
        # Query-string assertions are never accepted.
        assert client.post("/api/auth/piloop-sso?assertion=" + bridge.mint_owner_assertion(),
                           headers=origin, follow_redirects=False).status_code in (401, 415)
        assert client.get("/api/auth/me").json()["username"] == "guest_user"
        assert client.get("/api/admin/users").status_code == 403
    finally:
        client.close()
        bridge.close()
        forger.close()
        store.conn.close()


def test_migrated_admin_functions_work_through_bridge_and_are_closed_locally(tmp_path, monkeypatch):
    from src.web import app as appmod
    from src.web.auth import UserStore
    store = UserStore(tmp_path / "users.db")
    owner = store.create("owner_local", "owner-pass-1234", role="admin")
    other = store.create("other_admin", "other-pass-12345", role="admin")
    victim = store.create("leaving_user", "leaving-pass-1234", role="user")
    bridge = PiloopBridge(SECRET, tmp_path / "bridge.db")
    issuer = PiloopBridge(SECRET, tmp_path / "issuer.db")
    monkeypatch.setattr(appmod, "user_store", store)
    monkeypatch.setattr(appmod, "piloop_bridge", bridge)
    monkeypatch.setenv("PILOOP_SSO_ADMIN_USERNAME", "owner_local")
    monkeypatch.delenv("YARNENGINE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    client = TestClient(appmod.app)

    def call(payload, path="/api/piloop-bridge/v1"):
        body = json.dumps(payload).encode()
        headers = {"Content-Type": "application/json", **issuer.sign_api("POST", path, body)}
        return client.post(path, content=body, headers=headers)
    try:
        assert call({"action": "logs", "limit": 5}).status_code == 200
        assert call({"action": "ingestion_stats"}).status_code == 200
        vision = call({"action": "vision_get"}).json()
        assert "configured" in vision and "api_key" not in json.dumps(vision).lower().replace("key_", "")
        company = call({"action": "company_set", "company": {"company_name": "Test Ltd", "evil": "x"}})
        assert company.status_code == 200 and company.json()["company_name"] == "Test Ltd"
        assert call({"action": "company_get"}).json()["company_name"] == "Test Ltd"
        assert call({"action": "company_set", "company": {"company_name": "x" * 500}}).status_code == 422
        reset = call({"action": "update", "user_id": victim["id"], "password": "brand-new-pass-12345",
                      "email": "leaver@example.com"})
        assert reset.status_code == 200 and store.authenticate("leaving_user", "brand-new-pass-12345")
        assert call({"action": "delete", "user_id": owner["id"]}).status_code == 422
        assert call({"action": "delete", "user_id": victim["id"]}).status_code == 200
        assert store.get(victim["id"]) is None
        backup = call({"action": "backup"}, "/api/piloop-bridge/v1/backup")
        assert backup.status_code == 200 and backup.content[:2] == b"PK"
        body = b'{"action":"backup"}'
        stolen = issuer.sign_api("POST", "/api/piloop-bridge/v1", body)  # signed for another path
        assert client.post("/api/piloop-bridge/v1/backup", content=body,
                           headers={"Content-Type": "application/json", **stolen}).status_code == 403
        # The OpenCrochet Admin tab is gone while the bridge is active.
        assert client.post("/api/auth/login", json={"username": "other_admin",
                                                    "password": "other-pass-12345"}).status_code == 200
        assert client.get("/api/auth/me").json()["admin_console"] == "piloop"
        for method, path in (("get", "/api/admin/users"), ("get", "/api/admin/backup"),
                             ("get", "/api/admin/logs"), ("get", "/api/admin/ingestion/stats"),
                             ("get", "/api/admin/settings/vision"), ("get", "/api/admin/catalogue-roles"),
                             ("delete", f"/api/admin/users/{other['id']}")):
            assert getattr(client, method)(path).status_code == 403, path
        assert client.put("/api/admin/settings/company", json={"company_name": "y"}).status_code == 403
        assert client.get("/api/settings/company").status_code == 200  # public footer info still works
        # Break-glass: without the bridge the local administration returns.
        monkeypatch.setattr(appmod, "piloop_bridge", None)
        assert client.get("/api/auth/me").json()["admin_console"] == "local"
        assert client.get("/api/admin/users").status_code == 200
    finally:
        client.close()
        bridge.close()
        issuer.close()
        store.conn.close()


def test_piloop_signout_ends_opencrochet_session_and_sso_session_is_short(tmp_path, monkeypatch):
    from src.web import app as appmod
    from src.web.auth import UserStore
    import base64 as b64
    store = UserStore(tmp_path / "users.db")
    store.create("owner_local", "owner-pass-1234", role="admin")
    bridge = PiloopBridge(SECRET, tmp_path / "bridge.db")
    issuer = PiloopBridge(SECRET, tmp_path / "issuer.db")
    monkeypatch.setattr(appmod, "user_store", store)
    monkeypatch.setattr(appmod, "piloop_bridge", bridge)
    monkeypatch.setenv("PILOOP_SSO_ADMIN_USERNAME", "owner_local")
    monkeypatch.delenv("YARNENGINE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    client = TestClient(appmod.app)
    try:
        ok = client.post("/api/auth/piloop-sso", data={"assertion": issuer.mint_owner_assertion()},
                         headers={"Origin": "https://piloop.co.uk"}, follow_redirects=False)
        assert ok.status_code == 303 and "Max-Age=28800" in ok.headers["set-cookie"]
        token = client.cookies.get("ye_session")
        exp = int(b64.urlsafe_b64decode(token.encode()).decode().split(":")[1])
        assert exp - time.time() <= 8 * 3600 + 5
        assert client.get("/api/auth/me").status_code == 200
        assert client.post("/api/auth/piloop-signout", headers={"Origin": "https://evil.example"},
                           follow_redirects=False).status_code == 403
        assert client.get("/api/auth/me").status_code == 200
        out = client.post("/api/auth/piloop-signout", headers={"Origin": "https://piloop.co.uk"},
                          follow_redirects=False)
        assert out.status_code == 303 and out.headers["location"] == "https://piloop.co.uk/continue"
        assert client.get("/api/auth/me").status_code == 401
    finally:
        client.close()
        bridge.close()
        issuer.close()
        store.conn.close()


def test_password_change_and_reset_end_other_sessions_and_old_owner_cookies_are_revoked(tmp_path, monkeypatch):
    from src.web import app as appmod
    from src.web.auth import UserStore
    import base64 as b64, hmac as _hmac, hashlib as _hl
    store = UserStore(tmp_path / "users.db")
    owner = store.create("owner_local", "owner-pass-1234", role="admin")
    guest = store.create("guest_user", "guest-pass-12345", role="user")
    bridge = PiloopBridge(SECRET, tmp_path / "bridge.db")
    issuer = PiloopBridge(SECRET, tmp_path / "issuer.db")
    monkeypatch.setattr(appmod, "user_store", store)
    monkeypatch.setattr(appmod, "piloop_bridge", bridge)
    monkeypatch.setenv("PILOOP_SSO_ADMIN_USERNAME", "owner_local")
    monkeypatch.delenv("YARNENGINE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    # Isolate revocation stamps from other tests sharing the app's settings store.
    monkeypatch.setattr(appmod, "_SESSIONS_VALID_AFTER", f"auth.sessions_valid_after.{tmp_path.name}.")
    phone, laptop = TestClient(appmod.app), TestClient(appmod.app)
    try:
        # A pre-existing 30-day cookie in the old format (no issue time) for the owner.
        exp = int(time.time()) + 30 * 86400
        body = f"{owner['id']}:{exp}:{'ab' * 8}"
        sig = _hmac.new(appmod.session_signer.key, body.encode(), _hl.sha256).hexdigest()
        phone.cookies.set("ye_session", b64.urlsafe_b64encode(f"{body}:{sig}".encode()).decode())
        assert phone.get("/api/auth/me").status_code == 200
        appmod._revoke_sessions(owner["id"])  # what the one-time start-up reset does
        assert phone.get("/api/auth/me").status_code == 401
        # Password change signs out other devices but keeps the current one.
        for c in (phone, laptop):
            c.cookies.clear()
            time.sleep(1.1)
            assert c.post("/api/auth/login", json={"username": "guest_user",
                                                   "password": "guest-pass-12345"}).status_code == 200
        time.sleep(1.1)
        assert laptop.post("/api/auth/change-password", json={"current_password": "guest-pass-12345",
                                                              "new_password": "guest-new-pass-12345"}).status_code == 200
        assert laptop.get("/api/auth/me").status_code == 200
        assert phone.get("/api/auth/me").status_code == 401
        # Reset from PILOOP administration signs the user out everywhere.
        time.sleep(1.1)
        body = json.dumps({"action": "update", "user_id": guest["id"], "password": "reset-by-owner-12345"}).encode()
        r = laptop.post("/api/piloop-bridge/v1", content=body, headers={
            "Content-Type": "application/json", **issuer.sign_api("POST", "/api/piloop-bridge/v1", body)})
        assert r.status_code == 200
        assert laptop.get("/api/auth/me").status_code == 401
    finally:
        phone.close()
        laptop.close()
        bridge.close()
        issuer.close()
        store.conn.close()
