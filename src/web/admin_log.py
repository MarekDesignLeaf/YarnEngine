"""Persistent administrator-visible application log for OpenCrochet Pro (powered by YarnEngine core).

The log deliberately stores request metadata and diagnostic details, never request
bodies, passwords, API keys or session cookies.  A separate SQLite database keeps
logging independent from the application data while still living on the same
persistent Railway volume.
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from pathlib import Path
from typing import Any


class AdminLogStore:
    LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}
    MAX_ROWS = 50_000

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    event TEXT NOT NULL,
                    method TEXT,
                    path TEXT,
                    status_code INTEGER,
                    duration_ms REAL,
                    user_id INTEGER,
                    username TEXT,
                    role TEXT,
                    request_id TEXT,
                    message TEXT,
                    details_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_admin_logs_created
                    ON admin_logs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_admin_logs_level
                    ON admin_logs(level);
                CREATE INDEX IF NOT EXISTS idx_admin_logs_event
                    ON admin_logs(event);
                """
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _timestamp() -> str:
        return (
            _dt.datetime.now(_dt.timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

    def write(
        self,
        *,
        level: str = "INFO",
        event: str,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
        duration_ms: float | None = None,
        user_id: int | None = None,
        username: str | None = None,
        role: str | None = None,
        request_id: str | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        level = str(level or "INFO").upper()
        if level not in self.LEVELS:
            level = "INFO"
        event = str(event or "application")
        message = None if message is None else str(message)[:4000]
        details_json = None
        if details:
            details_json = json.dumps(details, ensure_ascii=False, default=str)
            if len(details_json) > 50_000:
                details_json = details_json[:50_000] + "…"

        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO admin_logs (
                    created_at, level, event, method, path, status_code,
                    duration_ms, user_id, username, role, request_id,
                    message, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._timestamp(),
                    level,
                    event,
                    method,
                    path,
                    status_code,
                    round(float(duration_ms), 2) if duration_ms is not None else None,
                    user_id,
                    username,
                    role,
                    request_id,
                    message,
                    details_json,
                ),
            )
            row_id = int(cur.lastrowid)
            if row_id > self.MAX_ROWS and row_id % 250 == 0:
                conn.execute(
                    "DELETE FROM admin_logs WHERE id <= ?",
                    (row_id - self.MAX_ROWS,),
                )
            conn.commit()
            return row_id
        finally:
            conn.close()

    def list(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        level: str | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        where: list[str] = []
        args: list[Any] = []

        if level:
            normalized = str(level).upper()
            if normalized not in self.LEVELS:
                raise ValueError("invalid log level")
            where.append("level = ?")
            args.append(normalized)

        if q:
            needle = f"%{str(q).strip()}%"
            where.append(
                "("
                "event LIKE ? OR path LIKE ? OR username LIKE ? OR "
                "message LIKE ? OR request_id LIKE ?"
                ")"
            )
            args.extend([needle] * 5)

        clause = (" WHERE " + " AND ".join(where)) if where else ""
        conn = self._connect()
        try:
            total = int(
                conn.execute(
                    "SELECT COUNT(*) FROM admin_logs" + clause,
                    args,
                ).fetchone()[0]
            )
            rows = conn.execute(
                "SELECT * FROM admin_logs"
                + clause
                + " ORDER BY id DESC LIMIT ? OFFSET ?",
                [*args, limit, offset],
            ).fetchall()
        finally:
            conn.close()

        items = []
        for row in rows:
            item = dict(row)
            raw_details = item.pop("details_json", None)
            if raw_details:
                try:
                    item["details"] = json.loads(raw_details)
                except json.JSONDecodeError:
                    item["details"] = {"raw": raw_details}
            else:
                item["details"] = None
            items.append(item)
        return {"items": items, "total": total, "limit": limit, "offset": offset}
