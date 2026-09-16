import pytest
from fastapi.testclient import TestClient
import src.web.app as appmod


@pytest.fixture
def two_users(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    from src.web.auth import UserStore
    store = UserStore(tmp_path / "users.sqlite")
    monkeypatch.setattr(appmod, "user_store", store)
    store.create("alice", "correct-horse-1", role="admin")
    store.create("bob", "another-pass-2", role="user")
    alice = TestClient(appmod.app)
    alice.post("/api/auth/login", json={"username": "alice", "password": "correct-horse-1"})
    bob = TestClient(appmod.app)
    bob.post("/api/auth/login", json={"username": "bob", "password": "another-pass-2"})
    return alice, bob


def _calc():
    return {"pattern_id": "STOCKINETTE", "pattern_version": "1.0.0", "yarn_id": None,
            "width_cm": 30, "height_cm": 30, "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 28,
            "allowance_percent": 8, "partial_repeat_mode": "reject",
            "edges": {"left_stitches": 0, "right_stitches": 0, "left_operation": "K", "right_operation": "K"},
            "calculation_mode": "geometry", "yarn_diameter_mm": 1.0}


def test_projects_are_scoped_to_their_owner(two_users):
    alice, bob = two_users
    p = alice.post("/api/projects", json={"name": "Alice's blanket", "calculation": _calc()}).json()
    pid = p["project_id"]

    # Alice sees it in her list and can open/update/delete it.
    assert any(x["project_id"] == pid for x in alice.get("/api/projects").json())
    assert alice.get(f"/api/projects/{pid}").status_code == 200

    # Bob cannot see, open, update, calculate or delete Alice's project.
    assert not any(x["project_id"] == pid for x in bob.get("/api/projects").json())
    assert bob.get(f"/api/projects/{pid}").status_code == 404
    assert bob.put(f"/api/projects/{pid}", json={"name": "Hijacked"}).status_code == 404
    assert bob.post(f"/api/projects/{pid}/calculate").status_code == 404
    assert bob.delete(f"/api/projects/{pid}").status_code == 404

    # Alice can still manage her own project.
    assert alice.put(f"/api/projects/{pid}", json={"name": "Renamed"}).status_code == 200
    assert alice.delete(f"/api/projects/{pid}").status_code == 200


def test_share_link_exposes_a_read_only_public_view(two_users):
    alice, bob = two_users
    p = alice.post("/api/projects", json={"name": "Shareable hat", "calculation": _calc()}).json()
    pid = p["project_id"]

    # Not shared yet: no token, and a guest has nothing to fetch.
    assert p.get("share_token") in (None, "")

    shared = alice.post(f"/api/projects/{pid}/share").json()
    token = shared["share_token"]
    assert token

    # Bob -- or anyone unauthenticated -- can read the public share view.
    from fastapi.testclient import TestClient
    guest = TestClient(appmod.app)
    r = guest.get(f"/api/share/{token}")
    assert r.status_code == 200
    assert r.json()["name"] == "Shareable hat"

    # Revoking the share token takes the public view away again.
    assert alice.delete(f"/api/projects/{pid}/share").status_code == 200
    assert guest.get(f"/api/share/{token}").status_code == 404


def test_share_token_requires_ownership(two_users):
    alice, bob = two_users
    p = alice.post("/api/projects", json={"name": "Alice's mittens", "calculation": _calc()}).json()
    assert bob.post(f"/api/projects/{p['project_id']}/share").status_code == 404
