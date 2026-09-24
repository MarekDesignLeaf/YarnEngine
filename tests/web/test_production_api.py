"""Production orders over the API.

The steps are the owner's own; nothing is assumed. An order keeps the steps it
started with, every move is recorded with who made it, and moves can be undone.
"""
import pytest
from fastapi.testclient import TestClient

import src.web.app as appmod
from src.production.store import ProductionStore


@pytest.fixture()
def team(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    from src.web.auth import UserStore
    monkeypatch.setattr(appmod, "user_store", UserStore(tmp_path / "users.sqlite"))
    monkeypatch.setattr(appmod, "production_store", ProductionStore(tmp_path / "production.sqlite"))
    admin = TestClient(appmod.app)
    admin.post("/api/auth/register", json={"username": "marek", "password": "correct-horse-1"})
    maker = TestClient(appmod.app)
    maker.post("/api/auth/register", json={"username": "eva", "password": "another-pass-22"})
    return admin, maker


def test_no_steps_are_invented(team):
    admin, _ = team
    assert admin.get("/api/production/stages").json() == {"stages": []}
    r = admin.post("/api/production/orders", json={"product_name": "Fox", "quantity": 1})
    assert r.status_code == 409 and "steps" in r.json()["detail"]


def test_only_admin_defines_steps(team):
    admin, maker = team
    assert maker.put("/api/admin/production/stages", json={"stages": ["A"]}).status_code == 403
    r = admin.put("/api/admin/production/stages", json={"stages": [" Step one ", "", "Step two"]})
    assert r.json() == {"stages": ["Step one", "Step two"]}
    assert admin.put("/api/admin/production/stages", json={"stages": ["A", "a"]}).status_code == 409


def test_order_moves_through_steps_with_audit(team):
    admin, maker = team
    admin.put("/api/admin/production/stages", json={"stages": ["One", "Two"]})
    o = maker.post("/api/production/orders", json={"product_name": "Fox", "quantity": 3, "note": "first batch"}).json()
    assert (o["current_stage"], o["steps_done"], o["steps_total"], o["status"]) == ("One", 0, 2, "open")
    o = maker.post(f"/api/production/orders/{o['order_id']}/advance").json()
    assert o["current_stage"] == "Two"
    o = admin.post(f"/api/production/orders/{o['order_id']}/advance", json={"note": "checked"}).json()
    assert o["status"] == "done" and o["steps_done"] == 2
    assert maker.post(f"/api/production/orders/{o['order_id']}/advance").status_code == 409
    o = admin.post(f"/api/production/orders/{o['order_id']}/back").json()
    assert (o["status"], o["current_stage"]) == ("open", "Two")
    actions = [(e["action"], e["username"], e["from_stage"], e["to_stage"]) for e in o["events"]]
    assert actions == [("created", "eva", None, "One"), ("advanced", "eva", "One", "Two"),
                       ("completed", "marek", "Two", None), ("reopened", "marek", None, "Two")]


def test_editing_steps_does_not_rewrite_running_orders(team):
    admin, maker = team
    admin.put("/api/admin/production/stages", json={"stages": ["One", "Two"]})
    o = maker.post("/api/production/orders", json={"product_name": "Fox", "quantity": 1}).json()
    admin.put("/api/admin/production/stages", json={"stages": ["Other"]})
    assert maker.get(f"/api/production/orders/{o['order_id']}").json()["stages"] == ["One", "Two"]


def test_cancel_needs_a_reason_and_bad_input_is_refused(team):
    admin, maker = team
    admin.put("/api/admin/production/stages", json={"stages": ["One"]})
    assert maker.post("/api/production/orders", json={"product_name": "Fox", "quantity": 0}).status_code == 409
    assert maker.post("/api/production/orders", json={"product_name": " ", "quantity": 1}).status_code == 409
    o = maker.post("/api/production/orders", json={"product_name": "Fox", "quantity": 1}).json()
    assert maker.post(f"/api/production/orders/{o['order_id']}/back").status_code == 409
    assert maker.post(f"/api/production/orders/{o['order_id']}/cancel").status_code == 409
    o = maker.post(f"/api/production/orders/{o['order_id']}/cancel", json={"reason": "yarn out of stock"}).json()
    assert o["status"] == "cancelled" and o["events"][-1]["note"] == "yarn out of stock"
    assert maker.get("/api/production/orders?status=open").json() == []
    assert maker.get("/api/production/orders/999").status_code == 404


def test_order_from_catalogue_product_takes_its_name(team):
    admin, maker = team
    admin.put("/api/admin/production/stages", json={"stages": ["One"]})
    lines = maker.get("/api/product-lines").json()
    assert maker.post("/api/production/orders", json={"product_line_id": 999999, "quantity": 1}).status_code == 404
    if lines:
        o = maker.post("/api/production/orders", json={"product_line_id": lines[0]["id"], "quantity": 2}).json()
        assert o["product_name"] == lines[0]["name"] and o["product_line_id"] == lines[0]["id"]
