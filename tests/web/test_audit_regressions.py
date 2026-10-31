"""Regression tests for the 2026-10-31 security and persistence audit."""
import io
import json
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

import src.web.app as appmod
from src.pricing import fetch as price_fetch
from src.pricing.fetch import CannotFetch
from src.storage.backup import build_backup_zip
from src.storage.sqlite_store import SQLiteStore
from src.web.auth import UserStore


def test_price_fetch_refuses_redirect_without_following_it(monkeypatch):
    monkeypatch.setattr(price_fetch, "_check_address", lambda host: None)

    class Redirect:
        status_code = 302

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class FakeSession:
        def get(self, url, **kwargs):
            assert kwargs["allow_redirects"] is False
            return Redirect()

    with pytest.raises(CannotFetch, match="redirected"):
        price_fetch.fetch("https://shop.example/yarn", session=FakeSession())


def test_password_reset_uses_trusted_origin_not_request_host(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    monkeypatch.setenv("YARNENGINE_PUBLIC_BASE_URL", "https://real.example")
    users = UserStore(tmp_path / "users.sqlite")
    users.create("resetuser", "test-password-123", email="reset@example.org")
    monkeypatch.setattr(appmod, "user_store", users)
    monkeypatch.setattr(appmod, "piloop_bridge", None)
    seen = {}
    monkeypatch.setattr(appmod, "send_email", lambda **kwargs: seen.update(kwargs))
    response = TestClient(appmod.app).post(
        "/api/auth/forgot-password", json={"username_or_email": "resetuser"},
        headers={"host": "evil.example"})
    assert response.status_code == 200
    assert "https://real.example/?reset_token=" in seen["html"]
    assert "evil.example" not in seen["html"]


def test_session_revocation_is_immediate_even_same_second(monkeypatch, tmp_path):
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    users = UserStore(tmp_path / "users.sqlite")
    users.create("instantuser", "test-password-123")
    monkeypatch.setattr(appmod, "user_store", users)
    monkeypatch.setattr(appmod, "piloop_bridge", None)
    monkeypatch.setattr(appmod, "_SESSIONS_VALID_AFTER", "audit.test.session.")
    client = TestClient(appmod.app)
    assert client.post("/api/auth/login",
                       json={"username": "instantuser", "password": "test-password-123"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    # No sleep: proves revocation is not vulnerable to same-second issuance.
    appmod._revoke_sessions(users.get_by_username("instantuser")["id"])
    assert client.get("/api/auth/me").status_code == 401


def test_editor_save_is_immediately_readable_and_durable(monkeypatch, tmp_path):
    db = tmp_path / "persistent" / "patterns.sqlite"
    monkeypatch.setattr(appmod.service, "_store", lambda: SQLiteStore(db))
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "1")
    client = TestClient(appmod.app)
    pattern = {"pattern_id": "AUDIT_SINGLE_STITCH", "version": "1.0.0",
               "name": "Audit test", "width": 1, "height": 1,
               "cells": [{"row": 1, "col": 1, "operation_id": "K", "span": 1}]}
    response = client.post("/api/editor/save", json={"pattern": pattern})
    assert response.status_code == 200, response.text
    assert response.json()["path"] is None
    found, name, family = appmod.service._pattern("AUDIT_SINGLE_STITCH", "1.0.0")
    assert name == "Audit test"
    assert client.post("/api/editor/save", json={"pattern": pattern}).status_code == 409
    assert db.exists()


def test_backup_includes_media_and_scrubs_actual_app_settings(tmp_path):
    database = tmp_path / "web_app.sqlite"
    with sqlite3.connect(database) as conn:
        conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO app_settings VALUES ('secret.anthropic_api_key', 'never-export')")
        conn.execute("INSERT INTO app_settings VALUES ('company.name', 'Safe')")
    media = tmp_path / "product_photos"
    media.mkdir()
    (media / "photo.png").write_bytes(b"test-image")
    (tmp_path / ".session_secret").write_text("never-export")
    blob = build_backup_zip(tmp_path)
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        assert "product_photos/photo.png" in zf.namelist()
        assert zf.read("product_photos/photo.png") == b"test-image"
        assert ".session_secret" not in zf.namelist()
        target = tmp_path / "restored.sqlite"
        target.write_bytes(zf.read("web_app.sqlite"))
    with sqlite3.connect(target) as conn:
        settings = dict(conn.execute("SELECT key,value FROM app_settings"))
    assert settings == {"company.name": "Safe"}


def test_service_worker_never_caches_private_pages():
    from pathlib import Path
    worker = Path(appmod.STATIC / "sw.js").read_text()
    assert 'SHELL.includes(u.pathname)' in worker
    assert "e.request.method" in worker
    assert 'u.origin!==self.location.origin' in worker
