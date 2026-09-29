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
        assert client.get("/api/auth/me").json()["username"] == "owner_local"
        assert client.get("/api/admin/users").status_code == 200
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
