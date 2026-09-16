from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from typing import Any

from src.import_pipeline.core import canonical_checksum
from src.storage.sqlite_store import SQLiteStore

from .models import ProductCandidate, SourceConfig, NormalizedYarn

INGESTION_SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS ingestion_sources(
  source_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  manufacturer_name TEXT,
  country TEXT,
  base_url TEXT,
  catalogue_urls_json TEXT NOT NULL,
  product_url_regex TEXT,
  exclude_url_regex TEXT,
  adapter TEXT NOT NULL,
  enabled INTEGER NOT NULL,
  domain_status TEXT NOT NULL,
  max_catalogue_pages INTEGER NOT NULL,
  max_product_pages INTEGER NOT NULL,
  delay_seconds REAL NOT NULL,
  robots_policy TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_runs(
  run_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  pages_fetched INTEGER NOT NULL DEFAULT 0,
  candidates_found INTEGER NOT NULL DEFAULT 0,
  imported_count INTEGER NOT NULL DEFAULT 0,
  review_count INTEGER NOT NULL DEFAULT 0,
  rejected_count INTEGER NOT NULL DEFAULT 0,
  error_count INTEGER NOT NULL DEFAULT 0,
  summary_json TEXT,
  FOREIGN KEY(source_id) REFERENCES ingestion_sources(source_id)
);

CREATE TABLE IF NOT EXISTS crawl_pages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  url TEXT NOT NULL,
  discovered_via TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  status_code INTEGER,
  content_type TEXT,
  sha256 TEXT,
  parser TEXT,
  UNIQUE(run_id,url),
  FOREIGN KEY(run_id) REFERENCES crawl_runs(run_id)
);

CREATE TABLE IF NOT EXISTS product_candidates(
  candidate_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  brand TEXT NOT NULL,
  product_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  discovered_via TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  normalized_json TEXT NOT NULL,
  active_evidence_json TEXT NOT NULL,
  confidence REAL NOT NULL,
  decision TEXT NOT NULL,
  reason TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(run_id,source_url),
  FOREIGN KEY(run_id) REFERENCES crawl_runs(run_id)
);

CREATE TABLE IF NOT EXISTS seed_reference_products(
  product_id TEXT PRIMARY KEY,
  brand TEXT NOT NULL,
  product_name TEXT NOT NULL,
  status TEXT,
  source_url TEXT,
  detail_level TEXT,
  raw_json TEXT NOT NULL,
  loaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS manual_review_queue(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  candidate_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'open',
  reason TEXT NOT NULL,
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  resolution_json TEXT,
  FOREIGN KEY(candidate_id) REFERENCES product_candidates(candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_sources_enabled ON ingestion_sources(enabled,domain_status);
CREATE INDEX IF NOT EXISTS idx_crawl_runs_source ON crawl_runs(source_id,started_at);
CREATE INDEX IF NOT EXISTS idx_candidate_decision ON product_candidates(decision,confidence);
CREATE INDEX IF NOT EXISTS idx_review_status ON manual_review_queue(status,created_at);
"""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class IngestionStore:
    def __init__(self, core: SQLiteStore):
        self.core = core
        self.conn = core.conn
        self.conn.execute("PRAGMA busy_timeout=10000")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(INGESTION_SCHEMA)
        self.conn.commit()

    def upsert_source(self, source: SourceConfig):
        now = utc_now()
        self.conn.execute("""
        INSERT INTO ingestion_sources(source_id,display_name,manufacturer_name,country,base_url,catalogue_urls_json,
          product_url_regex,exclude_url_regex,adapter,enabled,domain_status,max_catalogue_pages,max_product_pages,
          delay_seconds,robots_policy,notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(source_id) DO UPDATE SET
          display_name=excluded.display_name,manufacturer_name=excluded.manufacturer_name,country=excluded.country,
          base_url=excluded.base_url,catalogue_urls_json=excluded.catalogue_urls_json,
          product_url_regex=excluded.product_url_regex,exclude_url_regex=excluded.exclude_url_regex,
          adapter=excluded.adapter,enabled=excluded.enabled,domain_status=excluded.domain_status,
          max_catalogue_pages=excluded.max_catalogue_pages,max_product_pages=excluded.max_product_pages,
          delay_seconds=excluded.delay_seconds,robots_policy=excluded.robots_policy,notes=excluded.notes,updated_at=excluded.updated_at
        """, (
            source.source_id, source.display_name, source.manufacturer_name, source.country, source.base_url,
            json.dumps(list(source.catalogue_urls)), source.product_url_regex, source.exclude_url_regex, source.adapter,
            1 if source.enabled else 0, source.domain_status, source.max_catalogue_pages, source.max_product_pages,
            source.delay_seconds, source.robots_policy, source.notes, now, now,
        ))
        self.conn.commit()

    def start_run(self, source_id: str) -> str:
        run_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO crawl_runs(run_id,source_id,started_at,status) VALUES(?,?,?,'running')",
            (run_id, source_id, utc_now()),
        )
        self.conn.commit()
        return run_id

    def record_page(self, run_id: str, source_id: str, url: str, discovered_via: str, status_code: int, content_type: str, text: str):
        sha = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        self.conn.execute("""
        INSERT OR IGNORE INTO crawl_pages(run_id,source_id,url,discovered_via,fetched_at,status_code,content_type,sha256,parser)
        VALUES(?,?,?,?,?,?,?,?,?)
        """, (run_id, source_id, url, discovered_via, utc_now(), status_code, content_type, sha, "html/jsonld-v1"))
        self.conn.commit()

    def save_candidate(self, run_id: str, candidate: ProductCandidate, normalized: NormalizedYarn, decision: str, reason: str | None):
        candidate_id = hashlib.sha256(f"{run_id}|{candidate.source_url}".encode()).hexdigest()[:32]
        self.conn.execute("""
        INSERT OR REPLACE INTO product_candidates(candidate_id,run_id,source_id,brand,product_name,source_url,
          discovered_via,raw_json,normalized_json,active_evidence_json,confidence,decision,reason,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            candidate_id, run_id, candidate.source_id, candidate.brand, candidate.product_name, candidate.source_url,
            candidate.discovered_via, json.dumps(candidate.raw, ensure_ascii=False, sort_keys=True),
            json.dumps(normalized.to_dict(), ensure_ascii=False, sort_keys=True),
            json.dumps(candidate.active_evidence, ensure_ascii=False, sort_keys=True),
            candidate.confidence, decision, reason, utc_now(),
        ))
        if decision == "review":
            self.conn.execute("""
            INSERT OR IGNORE INTO manual_review_queue(candidate_id,status,reason,created_at) VALUES(?,'open',?,?)
            """, (candidate_id, reason or "manual review required", utc_now()))
        self.conn.commit()
        return candidate_id

    def import_to_core(self, normalized: NormalizedYarn):
        now = utc_now()
        d = normalized.core_dict()
        checksum = canonical_checksum(d)
        self.core.upsert_yarn(d, checksum, now)
        self.core.audit(
            entity_type="yarn", entity_id=d["yarn_id"], version=None,
            source_type=d["source_type"], source_reference=d["source_reference"],
            license_id=None, evidence_level=d["evidence_level"], checksum=checksum, imported_at=now,
        )

    def finish_run(self, run_id: str, status: str, summary: dict[str, Any]):
        self.conn.execute("""
        UPDATE crawl_runs SET finished_at=?,status=?,pages_fetched=?,candidates_found=?,imported_count=?,
          review_count=?,rejected_count=?,error_count=?,summary_json=? WHERE run_id=?
        """, (
            utc_now(), status, summary.get("pages_fetched", 0), summary.get("candidates_found", 0),
            summary.get("imported_count", 0), summary.get("review_count", 0), summary.get("rejected_count", 0),
            summary.get("error_count", 0), json.dumps(summary, ensure_ascii=False, sort_keys=True), run_id,
        ))
        self.conn.commit()

    def stats(self) -> dict[str, Any]:
        q = self.conn.execute
        return {
            "sources": q("SELECT COUNT(*) FROM ingestion_sources").fetchone()[0],
            "enabled_sources": q("SELECT COUNT(*) FROM ingestion_sources WHERE enabled=1").fetchone()[0],
            "runs": q("SELECT COUNT(*) FROM crawl_runs").fetchone()[0],
            "candidates": q("SELECT COUNT(*) FROM product_candidates").fetchone()[0],
            "open_reviews": q("SELECT COUNT(*) FROM manual_review_queue WHERE status='open'").fetchone()[0],
            "core_yarns": q("SELECT COUNT(*) FROM yarns").fetchone()[0],
            "seed_reference_products": q("SELECT COUNT(*) FROM seed_reference_products").fetchone()[0],
        }
