"""User accounts, password hashing and signed session cookies (stdlib only).

Passwords are stored as PBKDF2-HMAC-SHA256 hashes with a per-user random salt.
Sessions are HMAC-signed tokens carried in an HttpOnly cookie; nothing secret is
stored client-side. The first administrator is seeded from the environment
(ADMIN_USERNAME / ADMIN_PASSWORD) so no credential ever lives in the repository.
"""
import base64
import datetime
import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path

SESSION_COOKIE = "ye_session"
SESSION_DAYS = 30
PBKDF2_ITERATIONS = 200_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  last_login_at TEXT
);
"""


def _now():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return base64.b64encode(digest).decode(), base64.b64encode(salt).decode()


def verify_password(password: str, password_hash: str, salt_b64: str) -> bool:
    calc, _ = hash_password(password, base64.b64decode(salt_b64))
    return hmac.compare_digest(calc, password_hash)


def validate_username(username: str) -> str:
    u = (username or "").strip()
    if not (3 <= len(u) <= 32) or not all(c.isalnum() or c in "._-" for c in u):
        raise ValueError("username must be 3-32 characters: letters, digits, . _ -")
    return u


def validate_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    if len(password) > 256:
        raise ValueError("password too long")
    return password


class UserStore:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def get_by_username(self, username: str):
        r = self.conn.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
        return dict(r) if r else None

    def get(self, user_id: int):
        r = self.conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(r) if r else None

    def create(self, username: str, password: str, role: str = "user", active: bool = True):
        username = validate_username(username)
        password = validate_password(password)
        if role not in {"user", "admin"}:
            raise ValueError("invalid role")
        if self.get_by_username(username):
            raise ValueError("username already taken")
        h, s = hash_password(password)
        cur = self.conn.execute(
            "INSERT INTO users(username,password_hash,salt,role,active,created_at) VALUES(?,?,?,?,?,?)",
            (username, h, s, role, 1 if active else 0, _now()))
        self.conn.commit()
        return self.public(self.get(cur.lastrowid))

    def authenticate(self, username: str, password: str):
        u = self.get_by_username(username or "")
        if not u or not u["active"]:
            return None
        if not verify_password(password or "", u["password_hash"], u["salt"]):
            return None
        self.conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (_now(), u["id"]))
        self.conn.commit()
        return self.public(u)

    def set_password(self, user_id: int, password: str):
        password = validate_password(password)
        h, s = hash_password(password)
        self.conn.execute("UPDATE users SET password_hash=?,salt=? WHERE id=?", (h, s, user_id))
        self.conn.commit()

    def set_active(self, user_id: int, active: bool):
        self.conn.execute("UPDATE users SET active=? WHERE id=?", (1 if active else 0, user_id))
        self.conn.commit()

    def set_role(self, user_id: int, role: str):
        if role not in {"user", "admin"}:
            raise ValueError("invalid role")
        self.conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
        self.conn.commit()

    def delete(self, user_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def list(self):
        rows = self.conn.execute("SELECT * FROM users ORDER BY id").fetchall()
        return [self.public(dict(r)) for r in rows]

    def admin_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]

    @staticmethod
    def public(u):
        if u is None:
            return None
        return {"id": u["id"], "username": u["username"], "role": u["role"], "active": bool(u["active"]),
                "created_at": u["created_at"], "last_login_at": u.get("last_login_at")}

    def seed_admin_from_env(self):
        """Create the first administrator from ADMIN_USERNAME/ADMIN_PASSWORD if no users exist."""
        if self.count() > 0:
            return None
        username = os.environ.get("ADMIN_USERNAME", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not username or not password:
            return None
        return self.create(username, password, role="admin", active=True)


class SessionSigner:
    def __init__(self, secret: str):
        if not secret:
            raise ValueError("session secret required")
        self.key = secret.encode("utf-8")

    def issue(self, user_id: int, days: int = SESSION_DAYS) -> str:
        exp = int((datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).timestamp())
        nonce = secrets.token_hex(8)
        body = f"{user_id}:{exp}:{nonce}"
        sig = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode(f"{body}:{sig}".encode()).decode()

    def verify(self, token: str) -> int | None:
        try:
            raw = base64.urlsafe_b64decode(token.encode()).decode()
            user_id, exp, nonce, sig = raw.split(":")
            body = f"{user_id}:{exp}:{nonce}"
            expected = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, sig):
                return None
            if int(exp) < int(datetime.datetime.now(datetime.timezone.utc).timestamp()):
                return None
            return int(user_id)
        except Exception:
            return None


def session_secret_from_env(data_dir: Path) -> str:
    """Use SESSION_SECRET if set; otherwise persist a generated one next to the databases."""
    s = os.environ.get("SESSION_SECRET", "").strip()
    if s:
        return s
    p = Path(data_dir) / ".session_secret"
    if p.exists():
        return p.read_text().strip()
    p.parent.mkdir(parents=True, exist_ok=True)
    s = secrets.token_hex(32)
    p.write_text(s)
    return s
