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
