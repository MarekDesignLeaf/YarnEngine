"""Every calculated piece, written down on its own.

Nobody remembers to press Save, so the app does not ask: each successful
calculation is recorded as it happens, with the figures a person actually looks
up later -- what it was, which yarn and shade, how much yarn, how many balls --
and the full request and result kept alongside so an entry can be reopened and
recalculated exactly.

Two rules keep it honest rather than noisy:

* Pressing Calculate again on the same piece does not create a second entry. An
  identical request from the same person updates the one already there and
  counts the repeat, so the log is a list of pieces, not of clicks.
* A log belongs to the person who made it and is invisible to everyone else
  until they name a colleague to share it with. Sharing is per person, one at a
  time, and revoking it takes effect immediately.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS worklog(
  entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  yarn_id TEXT,
  yarn_name TEXT,
  colour_id TEXT,
  colour_name TEXT,
  colour_hex TEXT,
  length_m REAL,
  mass_g REAL,
  packages INTEGER,
  stitches INTEGER,
  pieces INTEGER,
  hook_mm REAL,
  gauge_stitches REAL,
  gauge_rows REAL,
  request_json TEXT NOT NULL,
  result_json TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  repeat_count INTEGER NOT NULL DEFAULT 1,
  private INTEGER NOT NULL DEFAULT 0,
  note TEXT
);

CREATE INDEX IF NOT EXISTS idx_worklog_user ON worklog(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_worklog_print ON worklog(user_id, fingerprint);
CREATE INDEX IF NOT EXISTS idx_worklog_yarn ON worklog(yarn_id);

CREATE TABLE IF NOT EXISTS worklog_shares(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  viewer_user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(owner_user_id, viewer_user_id)
);

CREATE INDEX IF NOT EXISTS idx_worklog_shares_viewer ON worklog_shares(viewer_user_id);

-- How far through making a piece someone is: which rounds are done, what the
-- counters say, and how long it has taken. Kept on the server rather than in
-- the browser because a piece is made over days, in a chair, on whichever
-- device is to hand -- and because the time it took is worth keeping.
CREATE TABLE IF NOT EXISTS worklog_progress(
  entry_id INTEGER PRIMARY KEY,
  user_id INTEGER,
  current_round INTEGER NOT NULL DEFAULT 0,
  done_json TEXT NOT NULL DEFAULT '[]',
  counters_json TEXT NOT NULL DEFAULT '[]',
  seconds REAL NOT NULL DEFAULT 0,
  running_since TEXT,
  finished_at TEXT,
  updated_at TEXT NOT NULL
);
"""

# How long an identical repeat folds into the entry already there rather than
# starting a new one. A day covers "I tweaked something else and calculated the
# same piece again"; next week's run is genuinely a new piece of work.
SAME_ENTRY_WINDOW_HOURS = 24

LIST_COLUMNS = (
    "entry_id, user_id, created_at, updated_at, kind, title, yarn_id, yarn_name, "
    "colour_id, colour_name, colour_hex, length_m, mass_g, packages, stitches, "
    "pieces, hook_mm, gauge_stitches, gauge_rows, repeat_count, private, note"
)


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def fingerprint(kind: str, request: dict) -> str:
    """What makes two calculations the same piece: the kind and every input."""
    raw = json.dumps({"kind": kind, "request": request}, sort_keys=True,
                     separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class WorkLogStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---- writing ------------------------------------------------------
    def record(self, *, user_id, kind, title, request, result, **fields):
        """Write one calculation down, or fold it into the identical one.

        Returns the stored row. Called from the calculate endpoints, where a
        failure must never cost the user their result, so callers wrap it.
        """
        print_ = fingerprint(kind, request)
        now = utc_now()
        cutoff = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(hours=SAME_ENTRY_WINDOW_HOURS)).isoformat()
        existing = self.conn.execute(
            "SELECT * FROM worklog WHERE user_id IS ? AND fingerprint=? AND updated_at>=? "
            "ORDER BY updated_at DESC LIMIT 1", (user_id, print_, cutoff)).fetchone()
        columns = {
            "yarn_id": None, "yarn_name": None, "colour_id": None, "colour_name": None,
            "colour_hex": None, "length_m": None, "mass_g": None, "packages": None,
            "stitches": None, "pieces": None, "hook_mm": None, "gauge_stitches": None,
            "gauge_rows": None,
        }
        columns.update({k: v for k, v in fields.items() if k in columns})
        # A log is read, not computed from, so the figures are stored at the
        # precision they are shown at -- 27.17 m, not 27.16741497698143.
        for key, places in (("length_m", 2), ("mass_g", 1), ("hook_mm", 2),
                            ("gauge_stitches", 1), ("gauge_rows", 1)):
            if columns[key] is not None:
                columns[key] = round(float(columns[key]), places)
        for key in ("packages", "stitches", "pieces"):
            if columns[key] is not None:
                columns[key] = int(columns[key])
        if existing is not None:
            self.conn.execute(
                "UPDATE worklog SET updated_at=?, title=?, result_json=?, "
                "repeat_count=repeat_count+1, " +
                ", ".join(f"{k}=?" for k in columns) + " WHERE entry_id=?",
                (now, title, json.dumps(result, ensure_ascii=False, default=str),
                 *columns.values(), existing["entry_id"]))
            self.conn.commit()
            return self.get(existing["entry_id"])
        cur = self.conn.execute(
            "INSERT INTO worklog(user_id, created_at, updated_at, kind, title, "
            "request_json, result_json, fingerprint, " + ", ".join(columns) + ") "
            "VALUES(?,?,?,?,?,?,?,?," + ",".join("?" for _ in columns) + ")",
            (user_id, now, now, kind, title,
             json.dumps(request, ensure_ascii=False, default=str),
             json.dumps(result, ensure_ascii=False, default=str),
             print_, *columns.values()))
        self.conn.commit()
        return self.get(cur.lastrowid)

    def update(self, entry_id, user_id, *, note=None, private=None, title=None):
        """Only the owner may change an entry."""
        row = self.get(entry_id)
        if row is None or row["user_id"] != user_id:
            return None
        sets, values = [], []
        if note is not None:
            sets.append("note=?"); values.append(note or None)
        if private is not None:
            sets.append("private=?"); values.append(1 if private else 0)
        if title:
            sets.append("title=?"); values.append(title)
        if not sets:
            return row
        self.conn.execute(f"UPDATE worklog SET {', '.join(sets)} WHERE entry_id=?",
                          (*values, entry_id))
        self.conn.commit()
        return self.get(entry_id)

    def delete(self, entry_id, user_id) -> bool:
        cur = self.conn.execute("DELETE FROM worklog WHERE entry_id=? AND user_id IS ?",
                                (entry_id, user_id))
        self.conn.commit()
        return cur.rowcount > 0

    # ---- reading ------------------------------------------------------
    def get(self, entry_id):
        row = self.conn.execute("SELECT * FROM worklog WHERE entry_id=?", (entry_id,)).fetchone()
        return dict(row) if row is not None else None

    def visible_entry(self, entry_id, viewer_id):
        """One entry, if the viewer owns it or its owner shares with them."""
        row = self.get(entry_id)
        if row is None:
            return None
        if row["user_id"] == viewer_id:
            return row
        if row["private"]:
            return None
        return row if self.shares_with(row["user_id"], viewer_id) else None

    def list(self, *, owner_id, viewer_id, query=None, kind=None, yarn_id=None,
             limit=200, offset=0):
        """A log, read by its owner or by someone it has been shared with."""
        own = owner_id == viewer_id
        if not own and not self.shares_with(owner_id, viewer_id):
            return None                       # not shared: nothing to see
        where = ["user_id IS ?"]
        params: list = [owner_id]
        if not own:
            where.append("private=0")
        if kind:
            where.append("kind=?"); params.append(kind)
        if yarn_id:
            where.append("yarn_id=?"); params.append(yarn_id)
        if query:
            where.append("(title LIKE ? OR IFNULL(yarn_name,'') LIKE ? OR "
                         "IFNULL(colour_name,'') LIKE ? OR IFNULL(note,'') LIKE ?)")
            params += [f"%{query}%"] * 4
        sql = (f"SELECT {LIST_COLUMNS} FROM worklog WHERE " + " AND ".join(where) +
               " ORDER BY updated_at DESC LIMIT ? OFFSET ?")
        rows = self.conn.execute(sql, (*params, max(1, min(int(limit), 500)), max(0, int(offset)))).fetchall()
        return [dict(r) for r in rows]

    def totals(self, *, owner_id, viewer_id):
        own = owner_id == viewer_id
        if not own and not self.shares_with(owner_id, viewer_id):
            return None
        extra = "" if own else " AND private=0"
        row = self.conn.execute(
            "SELECT COUNT(*) AS entries, IFNULL(SUM(length_m),0) AS length_m, "
            "IFNULL(SUM(mass_g),0) AS mass_g, IFNULL(SUM(stitches),0) AS stitches "
            f"FROM worklog WHERE user_id IS ?{extra}", (owner_id,)).fetchone()
        return dict(row)

    # ---- making it ----------------------------------------------------
    def progress(self, entry_id, user_id):
        """Where someone is in making a piece. Only the maker's own progress."""
        row = self.conn.execute(
            "SELECT * FROM worklog_progress WHERE entry_id=? AND user_id IS ?",
            (entry_id, user_id)).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["done"] = json.loads(out.pop("done_json"))
        out["counters"] = json.loads(out.pop("counters_json"))
        out["elapsed_seconds"] = self._elapsed(out)
        return out

    @staticmethod
    def _elapsed(row) -> float:
        """Seconds worked so far: what was banked, plus the running stretch.

        The clock is kept as a start time rather than ticked, so closing the
        app mid-round does not lose the time or invent any.
        """
        seconds = float(row["seconds"] or 0)
        if row.get("running_since"):
            started = datetime.datetime.fromisoformat(row["running_since"])
            now = datetime.datetime.now(datetime.timezone.utc)
            seconds += max(0.0, (now - started).total_seconds())
        return round(seconds, 1)

    def save_progress(self, entry_id, user_id, *, current_round=None, done=None,
                      counters=None, running=None, finished=None):
        entry = self.get(entry_id)
        if entry is None or entry["user_id"] != user_id:
            return None
        now = utc_now()
        row = self.conn.execute(
            "SELECT * FROM worklog_progress WHERE entry_id=?", (entry_id,)).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO worklog_progress(entry_id, user_id, updated_at) VALUES(?,?,?)",
                (entry_id, user_id, now))
            row = self.conn.execute(
                "SELECT * FROM worklog_progress WHERE entry_id=?", (entry_id,)).fetchone()
        row = dict(row)
        seconds, running_since = float(row["seconds"] or 0), row["running_since"]
        if running is not None:
            if running and not running_since:
                running_since = now
            elif not running and running_since:
                seconds = self._elapsed(row)       # bank the stretch just worked
                running_since = None
        sets = {"seconds": seconds, "running_since": running_since, "updated_at": now}
        if current_round is not None:
            sets["current_round"] = max(0, int(current_round))
        if done is not None:
            sets["done_json"] = json.dumps(sorted({int(x) for x in done}))
        if counters is not None:
            sets["counters_json"] = json.dumps(counters, ensure_ascii=False)
        if finished is not None:
            if finished and not row["finished_at"]:
                sets["finished_at"] = now
                # finishing stops the clock, so a piece left running overnight
                # does not keep counting after it is done
                sets["seconds"] = self._elapsed({**row, "running_since": running_since})
                sets["running_since"] = None
            elif not finished:
                sets["finished_at"] = None
        self.conn.execute(
            f"UPDATE worklog_progress SET {', '.join(f'{k}=?' for k in sets)} WHERE entry_id=?",
            (*sets.values(), entry_id))
        self.conn.commit()
        return self.progress(entry_id, user_id)

    def progress_for(self, entry_ids, user_id) -> dict:
        """A summary per entry, for showing time and how far along in a list."""
        if not entry_ids:
            return {}
        marks = ",".join("?" for _ in entry_ids)
        rows = self.conn.execute(
            f"SELECT * FROM worklog_progress WHERE user_id IS ? AND entry_id IN ({marks})",
            (user_id, *entry_ids)).fetchall()
        out = {}
        for r in rows:
            r = dict(r)
            out[r["entry_id"]] = {
                "elapsed_seconds": self._elapsed(r),
                "running": bool(r["running_since"]),
                "current_round": r["current_round"],
                "done_count": len(json.loads(r["done_json"])),
                "finished_at": r["finished_at"],
            }
        return out

    # ---- sharing ------------------------------------------------------
    def share(self, owner_id, viewer_id) -> bool:
        if owner_id == viewer_id:
            return False
        self.conn.execute(
            "INSERT OR IGNORE INTO worklog_shares(owner_user_id, viewer_user_id, created_at) "
            "VALUES(?,?,?)", (owner_id, viewer_id, utc_now()))
        self.conn.commit()
        return True

    def unshare(self, owner_id, viewer_id) -> bool:
        cur = self.conn.execute(
            "DELETE FROM worklog_shares WHERE owner_user_id=? AND viewer_user_id=?",
            (owner_id, viewer_id))
        self.conn.commit()
        return cur.rowcount > 0

    def shares_with(self, owner_id, viewer_id) -> bool:
        if owner_id is None or viewer_id is None:
            return False
        return self.conn.execute(
            "SELECT 1 FROM worklog_shares WHERE owner_user_id=? AND viewer_user_id=?",
            (owner_id, viewer_id)).fetchone() is not None

    def viewers_of(self, owner_id) -> list[int]:
        return [r["viewer_user_id"] for r in self.conn.execute(
            "SELECT viewer_user_id FROM worklog_shares WHERE owner_user_id=? ORDER BY created_at",
            (owner_id,))]

    def owners_for(self, viewer_id) -> list[int]:
        return [r["owner_user_id"] for r in self.conn.execute(
            "SELECT owner_user_id FROM worklog_shares WHERE viewer_user_id=? ORDER BY created_at",
            (viewer_id,))]
