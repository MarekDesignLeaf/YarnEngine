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
            CREATE TABLE IF NOT EXISTS catalogue_product_masters(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              product_line_id INTEGER NOT NULL,
              version INTEGER NOT NULL,
              state TEXT NOT NULL DEFAULT 'DRAFT',
              record_json TEXT NOT NULL,
              record_hash TEXT NOT NULL,
              created_by TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(product_line_id,version)
            );
            CREATE TABLE IF NOT EXISTS catalogue_assets(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              edition_id INTEGER NOT NULL,
              product_line_id INTEGER,
              asset_type TEXT NOT NULL,
              version INTEGER NOT NULL DEFAULT 1,
              state TEXT NOT NULL DEFAULT 'CANDIDATE',
              uri TEXT,
              sha256 TEXT,
              source_record_version TEXT,
              metadata_json TEXT NOT NULL DEFAULT '{}',
              created_by TEXT,
              created_at TEXT NOT NULL,
              UNIQUE(edition_id, asset_type, product_line_id, version),
              FOREIGN KEY(edition_id) REFERENCES catalogue_editions(id)
            );
            CREATE TABLE IF NOT EXISTS catalogue_validation_reports(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              asset_id INTEGER NOT NULL,
              asset_sha256 TEXT,
              policy_version TEXT NOT NULL,
              validator_id TEXT NOT NULL,
              validator_version TEXT NOT NULL,
              calibration_id TEXT,
              decision TEXT NOT NULL,
              checks_json TEXT NOT NULL,
              evidence_json TEXT NOT NULL DEFAULT '{}',
              created_by TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(asset_id) REFERENCES catalogue_assets(id)
            );
            CREATE TABLE IF NOT EXISTS catalogue_approvals(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              edition_id INTEGER NOT NULL,
              asset_id INTEGER,
              approval_type TEXT NOT NULL,
              decision TEXT NOT NULL,
              authority TEXT NOT NULL,
              evidence_ref TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(edition_id) REFERENCES catalogue_editions(id),
              FOREIGN KEY(asset_id) REFERENCES catalogue_assets(id)
            );
            CREATE TABLE IF NOT EXISTS catalogue_dependencies(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              edition_id INTEGER NOT NULL,
              upstream_kind TEXT NOT NULL,
              upstream_id INTEGER NOT NULL,
              upstream_version TEXT,
              downstream_kind TEXT NOT NULL,
              downstream_id INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(upstream_kind,upstream_id,upstream_version,downstream_kind,downstream_id),
              FOREIGN KEY(edition_id) REFERENCES catalogue_editions(id)
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

    def create_product_master(self, product_line_id:int, record:dict, record_hash:str, actor:str|None):
        if not record_hash: raise ValueError("Product Master Record hash is required")
        required=("product_id","variant_id","display_name")
        missing=[k for k in required if not record.get(k)]
        if missing: raise ValueError("incomplete Product Master Record: "+", ".join(missing))
        now=self._now()
        with self._conn() as c:
            r=c.execute("SELECT COALESCE(MAX(version),0)+1 AS v FROM catalogue_product_masters WHERE product_line_id=?",
                        (product_line_id,)).fetchone()
            version=int(r["v"])
            cur=c.execute("""INSERT INTO catalogue_product_masters
              (product_line_id,version,state,record_json,record_hash,created_by,created_at)
              VALUES(?,?,?,?,?,?,?)""",(product_line_id,version,"DRAFT",
              json.dumps(record,separators=(",",":"),sort_keys=True),record_hash,actor,now))
            return self.get_product_master(cur.lastrowid)

    def get_product_master(self, master_id:int):
        with self._conn() as c:
            r=c.execute("SELECT * FROM catalogue_product_masters WHERE id=?",(master_id,)).fetchone()
            if not r:return None
            d=dict(r);d["record"]=json.loads(d.pop("record_json"));return d

    def list_product_masters(self, product_line_id:int|None=None):
        with self._conn() as c:
            if product_line_id is None:
                rows=c.execute("SELECT * FROM catalogue_product_masters ORDER BY product_line_id,version DESC").fetchall()
            else:
                rows=c.execute("SELECT * FROM catalogue_product_masters WHERE product_line_id=? ORDER BY version DESC",
                               (product_line_id,)).fetchall()
            out=[]
            for r in rows:
                d=dict(r);d["record"]=json.loads(d.pop("record_json"));out.append(d)
            return out

    def approve_product_master(self, master_id:int, actor:str|None):
        m=self.get_product_master(master_id)
        if not m: raise KeyError("Product Master Record not found")
        if m["state"]!="DRAFT": raise ValueError("only DRAFT Product Master Record can be approved")
        now=self._now()
        with self._conn() as c:
            c.execute("""UPDATE catalogue_product_masters SET state='SUPERSEDED'
                         WHERE product_line_id=? AND state='APPROVED' AND id<>?""",(m["product_line_id"],master_id))
            c.execute("UPDATE catalogue_product_masters SET state='APPROVED' WHERE id=?",(master_id,))
        self.invalidate_dependencies("PRODUCT_MASTER",m["product_line_id"],str(m["version"]),actor)
        return self.get_product_master(master_id)

    def add_dependency(self, edition_id:int, upstream_kind:str, upstream_id:int, upstream_version:str|None,
                       downstream_kind:str, downstream_id:int):
        if downstream_kind not in {"ASSET","EDITION"}: raise ValueError("invalid downstream kind")
        now=self._now()
        with self._conn() as c:
            c.execute("""INSERT OR IGNORE INTO catalogue_dependencies
              (edition_id,upstream_kind,upstream_id,upstream_version,downstream_kind,downstream_id,created_at)
              VALUES(?,?,?,?,?,?,?)""",(edition_id,upstream_kind,upstream_id,upstream_version,
              downstream_kind,downstream_id,now))

    def list_dependencies(self, edition_id:int):
        with self._conn() as c:
            return [dict(r) for r in c.execute(
              "SELECT * FROM catalogue_dependencies WHERE edition_id=? ORDER BY id",(edition_id,)).fetchall()]

    def invalidate_dependencies(self, upstream_kind:str, upstream_id:int, current_version:str|None, actor:str|None):
        now=self._now(); affected_assets=[]; affected_editions=[]
        with self._conn() as c:
            rows=c.execute("""SELECT * FROM catalogue_dependencies
              WHERE upstream_kind=? AND upstream_id=? AND COALESCE(upstream_version,'')<>COALESCE(?, '')""",
              (upstream_kind,upstream_id,current_version)).fetchall()
            for r in rows:
                if r["downstream_kind"]=="ASSET":
                    a=c.execute("SELECT state,edition_id FROM catalogue_assets WHERE id=?",(r["downstream_id"],)).fetchone()
                    if a and a["state"] not in {"SUPERSEDED"}:
                        c.execute("UPDATE catalogue_assets SET state='STALE' WHERE id=?",(r["downstream_id"],))
                        affected_assets.append(r["downstream_id"])
                elif r["downstream_kind"]=="EDITION":
                    e=c.execute("SELECT state FROM catalogue_editions WHERE id=?",(r["downstream_id"],)).fetchone()
                    if e and e["state"] not in {"PUBLISHED","SUPERSEDED"}:
                        c.execute("UPDATE catalogue_editions SET state='BLOCKED',updated_at=? WHERE id=?",(now,r["downstream_id"]))
                        affected_editions.append(r["downstream_id"])
            editions=set(affected_editions)
            for aid in affected_assets:
                er=c.execute("SELECT edition_id FROM catalogue_assets WHERE id=?",(aid,)).fetchone()
                if er: editions.add(er["edition_id"])
            for eid in editions:
                c.execute("""INSERT INTO catalogue_events
                  (edition_id,event,actor,details_json,created_at) VALUES(?,?,?,?,?)""",
                  (eid,"dependency.invalidated",actor,json.dumps({"upstream_kind":upstream_kind,
                  "upstream_id":upstream_id,"current_version":current_version,
                  "assets":affected_assets},separators=(",",":")),now))
        return {"assets":affected_assets,"editions":affected_editions}

    def create_asset(self, edition_id: int, asset_type: str, product_line_id: int | None,
                     uri: str | None, sha256: str | None, actor: str | None,
                     metadata: dict | None=None, source_record_version: str | None=None):
        if not self.get(edition_id): raise KeyError("catalogue edition not found")
        if asset_type not in {"MASTER_VISUAL","PRODUCT_VIEW","CANONICAL_3D","PAGE","COVER","EXPORT"}:
            raise ValueError("unknown catalogue asset type")
        now=self._now()
        with self._conn() as c:
            r=c.execute("""SELECT COALESCE(MAX(version),0)+1 AS v FROM catalogue_assets
                WHERE edition_id=? AND asset_type=? AND product_line_id IS ?""",
                (edition_id,asset_type,product_line_id)).fetchone()
            version=int(r["v"])
            cur=c.execute("""INSERT INTO catalogue_assets
              (edition_id,product_line_id,asset_type,version,state,uri,sha256,source_record_version,
               metadata_json,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
              (edition_id,product_line_id,asset_type,version,"CANDIDATE",uri,sha256,source_record_version,
               json.dumps(metadata or {},separators=(",",":")),actor,now))
            aid=cur.lastrowid
        asset=self.get_asset(aid)
        if product_line_id is not None and source_record_version is not None:
            self.add_dependency(edition_id,"PRODUCT_MASTER",product_line_id,str(source_record_version),"ASSET",aid)
        return asset

    def get_asset(self, asset_id:int):
        with self._conn() as c:
            r=c.execute("SELECT * FROM catalogue_assets WHERE id=?",(asset_id,)).fetchone()
            if not r:return None
            d=dict(r);d["metadata"]=json.loads(d.pop("metadata_json") or "{}");return d

    def list_assets(self, edition_id:int):
        with self._conn() as c:
            rows=c.execute("SELECT * FROM catalogue_assets WHERE edition_id=? ORDER BY id",(edition_id,)).fetchall()
            out=[]
            for r in rows:
                d=dict(r);d["metadata"]=json.loads(d.pop("metadata_json") or "{}");out.append(d)
            return out

    def add_validation(self, asset_id:int, report:dict, actor:str|None):
        asset=self.get_asset(asset_id)
        if not asset: raise KeyError("catalogue asset not found")
        required=("policy_version","validator_id","validator_version","decision","checks")
        missing=[x for x in required if not report.get(x)]
        if missing: raise ValueError("incomplete validation report: "+", ".join(missing))
        decision=str(report["decision"]).upper()
        if decision=="PASS" and not report.get("evidence"):
            raise ValueError("PASS requires evidence")
        if decision=="PASS" and report.get("method") in {"AI","CV"} and not report.get("calibration_id"):
            raise ValueError("calibrated validator PASS requires calibration_id")
        if report.get("asset_sha256") != asset.get("sha256"):
            raise ValueError("validation asset hash mismatch")
        now=self._now()
        with self._conn() as c:
            cur=c.execute("""INSERT INTO catalogue_validation_reports
              (asset_id,asset_sha256,policy_version,validator_id,validator_version,calibration_id,
               decision,checks_json,evidence_json,created_by,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(asset_id,report.get("asset_sha256"),report["policy_version"],
              report["validator_id"],report["validator_version"],report.get("calibration_id"),decision,
              json.dumps(report["checks"],separators=(",",":")),
              json.dumps(report.get("evidence") or {},separators=(",",":")),actor,now))
            rid=cur.lastrowid
            if decision=="PASS":
                c.execute("UPDATE catalogue_assets SET state='VALIDATED' WHERE id=?",(asset_id,))
            elif decision=="FAIL":
                c.execute("UPDATE catalogue_assets SET state='FAILED' WHERE id=?",(asset_id,))
        return rid

    def add_approval(self, edition_id:int, approval_type:str, decision:str, authority:str,
                     evidence_ref:str|None=None, asset_id:int|None=None):
        if not self.get(edition_id): raise KeyError("catalogue edition not found")
        if decision not in {"APPROVED","NOT_APPLICABLE","REJECTED"}: raise ValueError("invalid approval decision")
        if not authority.strip(): raise ValueError("approval authority is required")
        now=self._now()
        with self._conn() as c:
            cur=c.execute("""INSERT INTO catalogue_approvals
              (edition_id,asset_id,approval_type,decision,authority,evidence_ref,created_at)
              VALUES(?,?,?,?,?,?,?)""",(edition_id,asset_id,approval_type,decision,authority,evidence_ref,now))
            return cur.lastrowid

    def approvals(self, edition_id:int):
        with self._conn() as c:
            return [dict(r) for r in c.execute(
              "SELECT * FROM catalogue_approvals WHERE edition_id=? ORDER BY id",(edition_id,)).fetchall()]

    def release_gates_ok(self, edition_id:int):
        approvals=self.approvals(edition_id)
        latest={}
        for a in approvals: latest[a["approval_type"]]=a
        for gate in ("IP_DISCLOSURE","COMPLIANCE"):
            a=latest.get(gate)
            if not a or a["decision"] not in {"APPROVED","NOT_APPLICABLE"}: return False
        return True

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
        if target=="RELEASE_APPROVED" and not self.release_gates_ok(edition_id):
            raise ValueError("IP disclosure and compliance approvals are required before release")
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
