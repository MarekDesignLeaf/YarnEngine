import pytest
from fastapi.testclient import TestClient

import src.web.app as appmod
from src.web.admin_log import AdminLogStore
from src.web.auth import UserStore


@pytest.fixture
def log_client(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    users = UserStore(tmp_path / "users.sqlite")
    logs = AdminLogStore(tmp_path / "admin_logs.sqlite")
    monkeypatch.setattr(appmod, "user_store", users)
    monkeypatch.setattr(appmod, "admin_log_store", logs)
    return TestClient(appmod.app), users, logs


def test_admin_log_store_persists_and_filters(tmp_path):
    store = AdminLogStore(tmp_path / "logs.sqlite")
    store.write(
        level="ERROR",
        event="test.failure",
        method="GET",
        path="/api/test",
        status_code=500,
        username="marek",
        message="boom",
        details={"exception": "RuntimeError"},
    )
    result = store.list(level="error", q="boom")
    assert result["total"] == 1
    assert result["items"][0]["event"] == "test.failure"
    assert result["items"][0]["details"]["exception"] == "RuntimeError"


def test_only_admin_can_view_logs_and_requests_are_recorded(log_client):
    client, users, _ = log_client
    users.create("marek", "correct-horse-1", role="admin")
    users.create("eva", "another-pass-2", role="user")

    admin = TestClient(appmod.app)
    assert admin.post(
        "/api/auth/login",
        json={"username": "marek", "password": "correct-horse-1"},
    ).status_code == 200
    assert admin.get("/api/patterns").status_code == 200

    response = admin.get("/api/admin/logs")
    assert response.status_code == 200
    rows = response.json()["items"]
    assert any(
        row["event"] == "http.request"
        and row["path"] == "/api/patterns"
        and row["username"] == "marek"
        and row["status_code"] == 200
        for row in rows
    )
    assert any(
        row["event"] == "auth.login.success" and row["username"] == "marek"
        for row in rows
    )

    regular = TestClient(appmod.app)
    assert regular.post(
        "/api/auth/login",
        json={"username": "eva", "password": "another-pass-2"},
    ).status_code == 200
    assert regular.get("/api/admin/logs").status_code == 403
