"""PILOOP-to-OpenCrochet server bridge. Disabled until a shared Railway secret is configured.

The invitation password and PILOOP owner session cookie never leave PILOOP.
Owner SSO uses a one-minute signed assertion in a cross-origin POST body.
Administrative API uses signed, nonce-bound requests over HTTPS. Replay IDs persist
in SQLite so restarting the process does not permit a second redemption.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class PiloopBridge:
    def __init__(self, secret: str, path: Path, now=None):
        if len(secret.encode("utf8")) < 32:
            raise ValueError("PILOOP_BRIDGE_SECRET must be at least 32 UTF-8 bytes")
        self.key = secret.encode("utf8")
        self.now = now or time.time
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5)
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute("""CREATE TABLE IF NOT EXISTS used_nonces (
            nonce TEXT PRIMARY KEY, expires INTEGER NOT NULL
        )""")
        self.conn.commit()

    def _use_once(self, namespace: str, nonce: str, expiry: int):
        if not re.fullmatch(r"[a-zA-Z0-9_-]{16,100}", nonce):
            raise ValueError("invalid nonce")
        self.conn.execute("DELETE FROM used_nonces WHERE expires < ?", (int(self.now()),))
        try:
            self.conn.execute(
                "INSERT INTO used_nonces(nonce,expires) VALUES(?,?)",
                (namespace + ":" + nonce, expiry))
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("replayed request") from exc

    def mint_owner_assertion(self):
        now = int(self.now())
        claims = {"v": 1, "iss": "piloop.co.uk", "aud": "opencrochet-pro",
                  "sub": "owner", "iat": now, "exp": now + 60,
                  "jti": secrets.token_urlsafe(24)}
        data = _b64encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf8"))
        message = "v1." + data
        signature = hmac.new(self.key, message.encode("ascii"), hashlib.sha256).hexdigest()
        return message + "." + signature

    def redeem_owner_assertion(self, token: str):
        try:
            if len(token) > 2048:
                raise ValueError("invalid assertion size")
            version, encoded, received = token.split(".")
            if version != "v1" or not re.fullmatch(r"[0-9a-f]{64}", received):
                raise ValueError("invalid assertion format")
            expected = hmac.new(self.key, f"v1.{encoded}".encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, received):
                raise ValueError("invalid assertion signature")
            claims = json.loads(_b64decode(encoded))
            now = int(self.now())
            if not (claims.get("v") == 1 and claims.get("iss") == "piloop.co.uk"
                    and claims.get("aud") == "opencrochet-pro" and claims.get("sub") == "owner"
                    and isinstance(claims.get("iat"), int) and isinstance(claims.get("exp"), int)
                    and now - 10 <= claims["iat"] <= now + 10
                    and claims["iat"] <= now <= claims["exp"]
                    and claims["exp"] - claims["iat"] <= 60):
                raise ValueError("expired or invalid assertion")
            self._use_once("sso", claims["jti"], claims["exp"] + 5)
            return claims
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeError) as exc:
            raise ValueError("invalid, expired or reused PILOOP assertion") from exc

    def sign_api(self, method: str, path: str, body: bytes):
        now = str(int(self.now()))
        nonce = secrets.token_urlsafe(24)
        digest = hashlib.sha256(body).hexdigest()
        message = "\n".join((method.upper(), path, now, nonce, digest))
        signature = hmac.new(self.key, message.encode("utf8"), hashlib.sha256).hexdigest()
        return {"X-Piloop-Time": now, "X-Piloop-Nonce": nonce,
                "X-Piloop-Signature": signature}

    def verify_api(self, method: str, path: str, body: bytes, headers: dict):
        try:
            when = int(headers.get("x-piloop-time", ""))
            nonce = headers.get("x-piloop-nonce", "")
            signature = headers.get("x-piloop-signature", "")
            now = int(self.now())
            if abs(when - now) > 60 or len(body) > 8192 or not re.fullmatch(r"[0-9a-f]{64}", signature):
                raise ValueError("invalid bridge request")
            digest = hashlib.sha256(body).hexdigest()
            message = "\n".join((method.upper(), path, str(when), nonce, digest))
            expected = hmac.new(self.key, message.encode("utf8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise ValueError("invalid bridge signature")
            self._use_once("api", nonce, when + 120)
        except (TypeError, ValueError) as exc:
            raise ValueError("unauthorized PILOOP bridge request") from exc
