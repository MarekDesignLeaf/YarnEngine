"""Persistent storage for the OpenCrochet Pro Catalogue Factory.

The store deliberately keeps catalogue workflow data separate from crochet
calculation data. Approved and released records are never overwritten.
"""
from __future__ import annotations
import datetime as _dt
import json
import sqlite3
import hashlib
from pathlib import Path
from .multiview import VIEW_ORDER, neighbours, validate_view_metadata, identity_checks, consistency_checks
from .decision import decide
from .correction import choose_correction
from .threed import validate_canonical_3d, validate_360_manifest
from .state_machine_v1_5 import TRANSITIONS, TERMINAL_STATES, allowed_targets, select_transition

# Compatibility views backed by the normative v1.5 transition table.
EDITION_TRANSITIONS={}
for _t in TRANSITIONS:
    EDITION_TRANSITIONS.setdefault(_t.source,set()).add(_t.target)
EDITION_TERMINAL_STATES=set(TERMINAL_STATES)
for _terminal in EDITION_TERMINAL_STATES:
    EDITION_TRANSITIONS.setdefault(_terminal,set())



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
            CREATE TABLE IF NOT EXISTS catalogue_generation_runs(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              edition_id INTEGER NOT NULL,
              product_line_id INTEGER NOT NULL,
              asset_id INTEGER,
              provider_id TEXT NOT NULL,
              model_id TEXT NOT NULL,
              task TEXT NOT NULL,
              prompt_hash TEXT NOT NULL,
              parameters_json TEXT NOT NULL DEFAULT '{}',
              reference_json TEXT NOT NULL DEFAULT '[]',
              created_by TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(edition_id) REFERENCES catalogue_editions(id),
              FOREIGN KEY(asset_id) REFERENCES catalogue_assets(id)
            );
            CREATE TABLE IF NOT EXISTS catalogue_corrections(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              parent_asset_id INTEGER NOT NULL,
              candidate_asset_id INTEGER,
              action TEXT NOT NULL,
              reason TEXT NOT NULL,
              attempt INTEGER NOT NULL,
              created_by TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(parent_asset_id) REFERENCES catalogue_assets(id),
              FOREIGN KEY(candidate_asset_id) REFERENCES catalogue_assets(id)
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
            CREATE TABLE IF NOT EXISTS catalogue_360_manifests(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              edition_id INTEGER NOT NULL,
              product_line_id INTEGER NOT NULL,
              canonical_3d_asset_id INTEGER,
              manifest_json TEXT NOT NULL,
              manifest_hash TEXT NOT NULL,
              created_by TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY(edition_id) REFERENCES catalogue_editions(id),
              FOREIGN KEY(canonical_3d_asset_id) REFERENCES catalogue_assets(id)
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
            cols={r["name"] for r in c.execute("PRAGMA table_info(catalogue_editions)").fetchall()}
            for name in ("approved_at","exported_at","withdrawn_at"):
                if name not in cols:
                    c.execute(f"ALTER TABLE catalogue_editions ADD COLUMN {name} TEXT")
            acols={r["name"] for r in c.execute("PRAGMA table_info(catalogue_approvals)").fetchall()}
            if "actor" not in acols:
                c.execute("ALTER TABLE catalogue_approvals ADD COLUMN actor TEXT")
            if "subject_hash" not in acols:
                c.execute("ALTER TABLE catalogue_approvals ADD COLUMN subject_hash TEXT")
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
            master_id=cur.lastrowid
        # Read only after the INSERT transaction has committed. Reading through a
        # second connection from inside the transaction returned None on a fresh
        # database and made Product Master creation non-deterministically unusable.
        return self.get_product_master(master_id)

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
        metadata=dict(metadata or {})
        if asset_type=="MASTER_VISUAL":
            if product_line_id is None or source_record_version is None:
                raise ValueError("MASTER_VISUAL requires product and Product Master Record version")
            metadata.setdefault("role","authoritative_visual_reference")
        if asset_type=="CANONICAL_3D":
            if product_line_id is None or source_record_version is None:
                raise ValueError("CANONICAL_3D requires product and Product Master Record version")
            metadata=validate_canonical_3d(metadata)
        if asset_type=="PRODUCT_VIEW":
            if product_line_id is None or source_record_version is None:
                raise ValueError("PRODUCT_VIEW requires product and Product Master Record version")
            metadata=validate_view_metadata(metadata)
            master_visual_id=metadata.get("master_visual_id")
            master_visual=self.get_asset(int(master_visual_id)) if master_visual_id is not None else None
            if not master_visual or master_visual["asset_type"]!="MASTER_VISUAL" or master_visual["product_line_id"]!=product_line_id:
                raise ValueError("PRODUCT_VIEW requires Master Visual for the same product")
            if master_visual["state"] not in {"APPROVED","LOCKED","VALIDATED"}:
                raise ValueError("PRODUCT_VIEW requires validated or approved Master Visual")
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
               json.dumps(metadata,separators=(",",":")),actor,now))
            aid=cur.lastrowid
        asset=self.get_asset(aid)
        if product_line_id is not None and source_record_version is not None:
            self.add_dependency(edition_id,"PRODUCT_MASTER",product_line_id,str(source_record_version),"ASSET",aid)
        if asset_type=="PRODUCT_VIEW":
            self.add_dependency(edition_id,"ASSET",int(metadata["master_visual_id"]),
                                str(master_visual["version"]),"ASSET",aid)
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

    def lock_master_visual(self, asset_id:int, actor:str|None):
        a=self.get_asset(asset_id)
        if not a or a["asset_type"]!="MASTER_VISUAL": raise KeyError("Master Visual not found")
        if a["state"]!="VALIDATED": raise ValueError("Master Visual must PASS validation before lock")
        with self._conn() as c:
            old=[dict(r) for r in c.execute("""SELECT id,version FROM catalogue_assets
              WHERE edition_id=? AND product_line_id=? AND asset_type='MASTER_VISUAL'
              AND id<>? AND state IN ('APPROVED','LOCKED')""",
              (a["edition_id"],a["product_line_id"],asset_id)).fetchall()]
            c.execute("""UPDATE catalogue_assets SET state='SUPERSEDED'
              WHERE edition_id=? AND product_line_id=? AND asset_type='MASTER_VISUAL'
              AND id<>? AND state IN ('APPROVED','LOCKED')""",(a["edition_id"],a["product_line_id"],asset_id))
            c.execute("UPDATE catalogue_assets SET state='LOCKED' WHERE id=?",(asset_id,))
        # Dependants of a superseded Master Visual must never remain current.
        for prior in old:
            self.invalidate_dependencies("ASSET",prior["id"],"SUPERSEDED",actor)
        return self.get_asset(asset_id)

    def product_master_for_asset(self, asset:dict):
        if asset.get("product_line_id") is None or asset.get("source_record_version") is None:return None
        with self._conn() as c:
            r=c.execute("""SELECT * FROM catalogue_product_masters
              WHERE product_line_id=? AND version=?""",(asset["product_line_id"],int(asset["source_record_version"]))).fetchone()
            if not r:return None
            d=dict(r);d["record"]=json.loads(d.pop("record_json"));return d

    def validate_product_identity(self, asset_id:int, observation:dict, actor:str|None,
                                  validator_id="structured-identity",validator_version="1"):
        asset=self.get_asset(asset_id)
        if not asset or asset["asset_type"] not in {"MASTER_VISUAL","PRODUCT_VIEW"}:
            raise KeyError("visual catalogue asset not found")
        pm=self.product_master_for_asset(asset)
        if not pm: raise ValueError("Product Master Record dependency missing")
        result=identity_checks(pm["record"],observation)
        report={"asset_sha256":asset.get("sha256"),"policy_version":"identity-v1",
          "validator_id":validator_id,"validator_version":validator_version,
          "decision":result["decision"],"checks":result["checks"],
          "evidence":{"observation":observation},"method":"EXACT"}
        if result["decision"]=="BLOCKED":
            with self._conn() as c:c.execute("UPDATE catalogue_assets SET state='BLOCKED' WHERE id=?",(asset_id,))
            return {"decision":"BLOCKED","checks":result["checks"]}
        rid=self.add_validation(asset_id,report,actor)
        return {"validation_report_id":rid,**result}

    def view_graph(self, edition_id:int, product_line_id:int):
        assets=[a for a in self.list_assets(edition_id)
                if a["product_line_id"]==product_line_id and a["asset_type"]=="PRODUCT_VIEW"]
        latest={}
        for a in assets:
            token=a["metadata"].get("view_token")
            if token and (token not in latest or a["version"]>latest[token]["version"]):latest[token]=a
        nodes=[]
        for token in VIEW_ORDER:
            a=latest.get(token)
            nodes.append({"view_token":token,"asset":a,
                          "neighbours":list(neighbours(token))})
        return {"product_line_id":product_line_id,"nodes":nodes}

    def revalidation_scope_for_view(self, edition_id:int, product_line_id:int, view_token:str):
        token=str(view_token or "").upper()
        if token not in VIEW_ORDER: raise ValueError("unknown view token")
        graph=self.view_graph(edition_id,product_line_id)
        by={n["view_token"]:n["asset"] for n in graph["nodes"] if n["asset"]}
        scope=[token,*neighbours(token)]
        return {"view_tokens":scope,"asset_ids":[by[t]["id"] for t in scope if t in by]}

    def validate_view_consistency(self, edition_id:int, product_line_id:int, actor:str|None):
        graph=self.view_graph(edition_id,product_line_id)
        by={n["view_token"]:n["asset"] for n in graph["nodes"] if n["asset"]}
        results=[];seen=set()
        for token,a in by.items():
            for other in neighbours(token):
                if other not in by: continue
                edge=tuple(sorted((token,other)))
                if edge in seen: continue
                seen.add(edge)
                r=consistency_checks(a["metadata"].get("observation") or {},
                                     by[other]["metadata"].get("observation") or {})
                results.append({"views":list(edge),**r})
        required=set(VIEW_ORDER)
        missing=sorted(required-set(by))
        if missing: decision="BLOCKED"
        elif any(r["decision"]=="FAIL" for r in results): decision="FAIL"
        elif any(r["decision"]=="BLOCKED" for r in results): decision="BLOCKED"
        else: decision="PASS"
        return {"decision":decision,"missing_views":missing,"edges":results}

    def record_generation(self, edition_id:int, product_line_id:int, asset_id:int|None,
                          provider_id:str, model_id:str, task:str, prompt_hash:str,
                          parameters:dict, references:list|tuple, actor:str|None):
        now=self._now()
        if not provider_id or not model_id or not prompt_hash:raise ValueError("generation provenance incomplete")
        with self._conn() as c:
            cur=c.execute("""INSERT INTO catalogue_generation_runs
              (edition_id,product_line_id,asset_id,provider_id,model_id,task,prompt_hash,
               parameters_json,reference_json,created_by,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(edition_id,product_line_id,asset_id,provider_id,model_id,
              task,prompt_hash,json.dumps(parameters or {},separators=(",",":")),
              json.dumps(list(references or []),separators=(",",":")),actor,now))
            return cur.lastrowid

    def generation_runs(self, edition_id:int):
        with self._conn() as c:
            rows=c.execute("SELECT * FROM catalogue_generation_runs WHERE edition_id=? ORDER BY id",
                           (edition_id,)).fetchall()
            out=[]
            for r in rows:
                d=dict(r);d["parameters"]=json.loads(d.pop("parameters_json") or "{}")
                d["references"]=json.loads(d.pop("reference_json") or "[]");out.append(d)
            return out

    def validation_history(self, asset_id:int):
        with self._conn() as c:
            rows=c.execute("SELECT * FROM catalogue_validation_reports WHERE asset_id=? ORDER BY id",
                           (asset_id,)).fetchall()
            out=[]
            for r in rows:
                d=dict(r);d["checks"]=json.loads(d.pop("checks_json") or "[]")
                d["evidence"]=json.loads(d.pop("evidence_json") or "{}");out.append(d)
            return out

    def decide_and_add_validation(self, asset_id:int, policy:dict, results:list[dict], actor:str|None,
                                  validator_id:str="decision-engine",validator_version:str="1"):
        asset=self.get_asset(asset_id)
        if not asset:raise KeyError("catalogue asset not found")
        outcome=decide(policy,results)
        report={"asset_sha256":asset.get("sha256"),"policy_version":policy.get("policy_version") if policy else "MISSING",
                "validator_id":validator_id,"validator_version":validator_version,
                "decision":outcome["decision"],"checks":results,
                "evidence":{"decision_engine":outcome},"method":"EXACT"}
        if outcome["decision"]=="PASS":
            rid=self.add_validation(asset_id,report,actor)
        elif outcome["decision"]=="FAIL":
            rid=self.add_validation(asset_id,report,actor)
        else:
            rid=None
            with self._conn() as c:
                c.execute("UPDATE catalogue_assets SET state=? WHERE id=?",
                          ("HUMAN_REVIEW" if outcome["decision"]=="NEEDS_REVIEW" else "BLOCKED",asset_id))
        return {"validation_report_id":rid,**outcome,"asset":self.get_asset(asset_id)}

    def plan_correction(self, asset_id:int, failed_checks:list[dict], actor:str|None,
                        local_edit_allowed:bool=True,max_regenerations:int=2):
        asset=self.get_asset(asset_id)
        if not asset:raise KeyError("catalogue asset not found")
        with self._conn() as c:
            history=[dict(r) for r in c.execute(
              "SELECT * FROM catalogue_corrections WHERE parent_asset_id=? ORDER BY id",(asset_id,)).fetchall()]
        plan=choose_correction(asset_id,failed_checks,history,local_edit_allowed,max_regenerations)
        now=self._now()
        with self._conn() as c:
            cur=c.execute("""INSERT INTO catalogue_corrections
              (parent_asset_id,action,reason,attempt,created_by,created_at)
              VALUES(?,?,?,?,?,?)""",(asset_id,plan.action,plan.reason,plan.attempt,actor,now))
            cid=cur.lastrowid
        return {"correction_id":cid,"action":plan.action,"reason":plan.reason,
                "attempt":plan.attempt,"parent_asset_id":asset_id}

    def attach_correction_candidate(self, correction_id:int, candidate_asset_id:int):
        candidate=self.get_asset(candidate_asset_id)
        if not candidate:raise KeyError("candidate asset not found")
        with self._conn() as c:
            r=c.execute("SELECT * FROM catalogue_corrections WHERE id=?",(correction_id,)).fetchone()
            if not r:raise KeyError("correction not found")
            if r["candidate_asset_id"] is not None:raise ValueError("correction already has a candidate")
            parent=self.get_asset(r["parent_asset_id"])
            if parent and parent["id"]==candidate_asset_id:raise ValueError("correction must create a new candidate")
            c.execute("UPDATE catalogue_corrections SET candidate_asset_id=? WHERE id=?",
                      (candidate_asset_id,correction_id))
        return candidate

    def register_360(self, edition_id:int, product_line_id:int, manifest:dict, actor:str|None):
        if not self.get(edition_id):raise KeyError("catalogue edition not found")
        m=validate_360_manifest(manifest)
        canonical_id=m.get("canonical_3d_asset_id")
        if m["source"]=="CANONICAL_3D":
            asset=self.get_asset(int(canonical_id))
            if not asset or asset["edition_id"]!=edition_id or asset["product_line_id"]!=product_line_id:
                raise ValueError("Canonical 3D asset does not match edition/product")
            if asset["asset_type"]!="CANONICAL_3D" or asset["state"] not in {"VALIDATED","APPROVED","LOCKED"}:
                raise ValueError("Canonical 3D source must be validated")
        import hashlib
        raw=json.dumps(m,sort_keys=True,separators=(",",":")).encode("utf-8")
        digest=hashlib.sha256(raw).hexdigest();now=self._now()
        with self._conn() as c:
            cur=c.execute("""INSERT INTO catalogue_360_manifests
              (edition_id,product_line_id,canonical_3d_asset_id,manifest_json,manifest_hash,created_by,created_at)
              VALUES(?,?,?,?,?,?,?)""",(edition_id,product_line_id,canonical_id,
              raw.decode("utf-8"),digest,actor,now))
            mid=cur.lastrowid
        if canonical_id:
            self.add_dependency(edition_id,"ASSET",int(canonical_id),str(self.get_asset(int(canonical_id))["version"]),
                                "EDITION",edition_id)
        return {"id":mid,"manifest":m,"manifest_hash":digest}

    def list_360(self, edition_id:int):
        with self._conn() as c:
            rows=c.execute("SELECT * FROM catalogue_360_manifests WHERE edition_id=? ORDER BY id",
                           (edition_id,)).fetchall()
            out=[]
            for r in rows:
                d=dict(r);d["manifest"]=json.loads(d.pop("manifest_json"));out.append(d)
            return out

    def lock_asset(self, asset_id:int):
        a=self.get_asset(asset_id)
        if not a:raise KeyError("catalogue asset not found")
        if a["state"]!="VALIDATED":raise ValueError("asset must be VALIDATED before lock")
        with self._conn() as c:c.execute("UPDATE catalogue_assets SET state='LOCKED' WHERE id=?",(asset_id,))
        return self.get_asset(asset_id)

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
            elif decision=="NEEDS_REVIEW":
                c.execute("UPDATE catalogue_assets SET state='HUMAN_REVIEW' WHERE id=?",(asset_id,))
            else:
                c.execute("UPDATE catalogue_assets SET state='BLOCKED' WHERE id=?",(asset_id,))
        return rid

    def _edition_subject_hash(self, edition_id:int):
        row=self.get(edition_id)
        if not row: raise KeyError("catalogue edition not found")
        raw=json.dumps(row["manifest"],sort_keys=True,separators=(",",":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def add_approval(self, edition_id:int, approval_type:str, decision:str, authority:str,
                     evidence_ref:str|None=None, asset_id:int|None=None, actor:str|None=None):
        if not self.get(edition_id): raise KeyError("catalogue edition not found")
        if decision not in {"APPROVED","NOT_APPLICABLE","REJECTED"}: raise ValueError("invalid approval decision")
        if not authority: raise ValueError("approval authority is required")
        subject_hash=self._edition_subject_hash(edition_id)
        now=self._now()
        with self._conn() as c:
            cur=c.execute("""INSERT INTO catalogue_approvals
              (edition_id,asset_id,approval_type,decision,authority,evidence_ref,created_at,actor,subject_hash)
              VALUES(?,?,?,?,?,?,?,?,?)""",
              (edition_id,asset_id,approval_type,decision,authority,evidence_ref,now,actor,subject_hash))
            return cur.lastrowid

    def approvals(self, edition_id:int):
        with self._conn() as c:
            return [dict(r) for r in c.execute(
              "SELECT * FROM catalogue_approvals WHERE edition_id=? ORDER BY id",(edition_id,)).fetchall()]

    def release_gates_ok(self, edition_id:int):
        current_hash=self._edition_subject_hash(edition_id)
        approvals=self.approvals(edition_id)
        latest={}
        for a in approvals:
            if a.get("subject_hash")==current_hash:
                latest[a["approval_type"]]=a
        for gate in ("IP_DISCLOSURE","COMPLIANCE"):
            a=latest.get(gate)
            if not a or a["decision"] not in {"APPROVED","NOT_APPLICABLE"}: return False
        return True

    def transition(self, edition_id:int, target:str, actor:str|None, details:dict|None=None,
                   actor_role:str="ORCHESTRATOR", trigger:str|None=None):
        row=self.get(edition_id)
        if not row: raise KeyError("catalogue edition not found")
        source=row["state"]
        spec=select_transition(source,target,actor_role,trigger)
        if target=="RELEASE_APPROVED" and not self.release_gates_ok(edition_id):
            raise ValueError("IP disclosure and compliance approvals are required before release approval")
        now=self._now()
        approved_at=now if target=="RELEASE_APPROVED" else row.get("approved_at")
        exported_at=now if target=="EXPORTED" else row.get("exported_at")
        released_at=now if target=="RELEASED" else row.get("released_at")
        withdrawn_at=now if target=="WITHDRAWN" else row.get("withdrawn_at")
        audit=dict(details or {})
        audit.update({"transition_id":spec.id,"trigger":spec.trigger,"guard":spec.guard,
                      "actor_role":actor_role,"gate":spec.gate})
        with self._conn() as c:
            c.execute("""UPDATE catalogue_editions SET state=?,updated_at=?,approved_at=?,exported_at=?,
                         released_at=?,withdrawn_at=? WHERE id=?""",
                      (target,now,approved_at,exported_at,released_at,withdrawn_at,edition_id))
            c.execute("""INSERT INTO catalogue_events
              (edition_id,event,from_state,to_state,actor,details_json,created_at)
              VALUES(?,?,?,?,?,?,?)""",
              (edition_id,"state.changed",source,target,actor,json.dumps(audit,separators=(",",":")),now))
        return self.get(edition_id)
