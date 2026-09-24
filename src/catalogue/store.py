"""Persistent storage for the OpenCrochet Pro Catalogue Factory.

The store deliberately keeps catalogue workflow data separate from crochet
calculation data. Approved and released records are never overwritten.
"""
from __future__ import annotations
import datetime as _dt
import json
import sqlite3
from pathlib import Path


class CatalogueStore:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._init()

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def _init(self):
        with self._conn() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS catalogue_editions(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              subtitle TEXT,
              locale TEXT NOT NULL DEFAULT 'en-GB',
              page_format TEXT NOT NULL DEFAULT 'A4',
              state TEXT NOT NULL DEFAULT 'DRAFT',
              manifest_json TEXT NOT NULL,
              created_by TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              released_at TEXT
            );
            CREATE TABLE IF NOT EXISTS catalogue_events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              edition_id INTEGER NOT NULL,
              event TEXT NOT NULL,
              from_state TEXT,
              to_state TEXT,
              actor TEXT,
              details_json TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(edition_id) REFERENCES catalogue_editions(id)
            );
            """)
    @staticmethod
    def _now():
        return _dt.datetime.now(_dt.timezone.utc).isoformat()

    @staticmethod
    def _row(r):
        if r is None: return None
        d = dict(r)
        d["manifest"] = json.loads(d.pop("manifest_json"))
        return d

    def create(self, manifest: dict, actor: str | None):
        now = self._now()
        with self._conn() as c:
            cur = c.execute("""INSERT INTO catalogue_editions
              (title,subtitle,locale,page_format,state,manifest_json,created_by,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              (manifest["title"], manifest.get("subtitle"), manifest.get("locale","en-GB"),
               manifest.get("format","A4"), "DRAFT", json.dumps(manifest, separators=(",",":")),
               actor, now, now))
            eid = cur.lastrowid
            c.execute("""INSERT INTO catalogue_events
              (edition_id,event,to_state,actor,details_json,created_at)
              VALUES(?,?,?,?,?,?)""",(eid,"edition.created","DRAFT",actor,"{}",now))
        return self.get(eid)

    def get(self, edition_id: int):
        with self._conn() as c:
            return self._row(c.execute("SELECT * FROM catalogue_editions WHERE id=?",(edition_id,)).fetchone())

    def list(self):
        with self._conn() as c:
            return [self._row(r) for r in c.execute("SELECT * FROM catalogue_editions ORDER BY id DESC").fetchall()]

    def events(self, edition_id: int):
        with self._conn() as c:
            rows=c.execute("SELECT * FROM catalogue_events WHERE edition_id=? ORDER BY id",(edition_id,)).fetchall()
            out=[]
            for r in rows:
                d=dict(r); d["details"]=json.loads(d.pop("details_json") or "{}"); out.append(d)
            return out

    def transition(self, edition_id: int, target: str, actor: str | None, details: dict | None=None):
        allowed={
          "DRAFT":{"INTERIOR_BUILDING","BLOCKED","SUPERSEDED"},
          "INTERIOR_BUILDING":{"INTERIOR_VALIDATING","BLOCKED","CHANGE_REQUESTED"},
          "INTERIOR_VALIDATING":{"INTERIOR_LOCKED","FAILED","BLOCKED","HUMAN_REVIEW"},
          "FAILED":{"CORRECTING","SUPERSEDED"},
          "CORRECTING":{"INTERIOR_VALIDATING","BLOCKED"},
          "HUMAN_REVIEW":{"INTERIOR_LOCKED","CORRECTING","BLOCKED"},
          "INTERIOR_LOCKED":{"COVER_BUILDING","CHANGE_REQUESTED"},
          "COVER_BUILDING":{"COVER_VALIDATING","BLOCKED"},
          "COVER_VALIDATING":{"FINAL_VALIDATING","FAILED","BLOCKED","HUMAN_REVIEW"},
          "FINAL_VALIDATING":{"RELEASE_APPROVED","FAILED","BLOCKED","HUMAN_REVIEW"},
          "CHANGE_REQUESTED":{"DRAFT","SUPERSEDED"},
          "BLOCKED":{"DRAFT","CORRECTING","SUPERSEDED"},
          "RELEASE_APPROVED":{"EXPORTED","PUBLISHED"},
          "EXPORTED":{"PUBLISHED"},
          "PUBLISHED":set(),"SUPERSEDED":set()
        }
        row=self.get(edition_id)
        if not row: raise KeyError("catalogue edition not found")
        source=row["state"]
        if target not in allowed.get(source,set()):
            raise ValueError(f"invalid catalogue transition {source} -> {target}")
        now=self._now()
        with self._conn() as c:
            c.execute("UPDATE catalogue_editions SET state=?,updated_at=?,released_at=CASE WHEN ?='RELEASE_APPROVED' THEN ? ELSE released_at END WHERE id=?",
                      (target,now,target,now,edition_id))
            c.execute("""INSERT INTO catalogue_events
              (edition_id,event,from_state,to_state,actor,details_json,created_at)
              VALUES(?,?,?,?,?,?,?)""",(edition_id,"state.changed",source,target,actor,json.dumps(details or {},separators=(",",":")),now))
        return self.get(edition_id)
