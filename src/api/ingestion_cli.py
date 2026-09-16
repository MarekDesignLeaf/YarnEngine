from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.yarn_ingestion.registry import load_registry, by_id
from src.yarn_ingestion.runner import IngestionRunner
from src.yarn_ingestion.seed import import_seed_jsonl


def main():
    p = argparse.ArgumentParser(description="YarnEngine automated current-catalogue ingestion")
    p.add_argument("--db", default="data/db/yarn_engine.sqlite")
    p.add_argument("--registry", default="data/ingestion/sources.json")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    ls = sub.add_parser("sources")
    ls.add_argument("--enabled-only", action="store_true")
    cs = sub.add_parser("crawl-source")
    cs.add_argument("source_id")
    ca = sub.add_parser("crawl-all")
    ca.add_argument("--limit", type=int)
    ca.add_argument("--workers", type=int, default=8)
    seed = sub.add_parser("seed-existing")
    seed.add_argument("--file", default="data/ingestion/seed_current_products_v0_5.jsonl")
    rv = sub.add_parser("review")
    rv.add_argument("--limit", type=int, default=100)
    args = p.parse_args()

    sources = load_registry(args.registry)
    runner = IngestionRunner(args.db)
    try:
        runner.register_sources(sources)
        if args.cmd == "init":
            out = {"registered_sources": len(sources), **runner.store.stats()}
        elif args.cmd == "status":
            out = runner.store.stats()
        elif args.cmd == "sources":
            selected = [s.to_dict() for s in sources if (s.enabled or not args.enabled_only)]
            out = {"count": len(selected), "sources": selected}
        elif args.cmd == "crawl-source":
            source = by_id(sources).get(args.source_id)
            if not source:
                raise SystemExit(f"unknown source_id {args.source_id}")
            out = runner.crawl_source(source)
        elif args.cmd == "crawl-all":
            from concurrent.futures import ThreadPoolExecutor, as_completed
            selected = [s for s in sources if s.enabled and s.domain_status == "verified"]
            if args.limit:
                selected = selected[:args.limit]
            # The main runner has already registered sources. Each worker opens its own SQLite connection.
            # WAL + busy_timeout allow independent source domains to be crawled concurrently.
            def work(source):
                r = IngestionRunner(args.db)
                try:
                    return r.crawl_source(source)
                finally:
                    r.close()
            runs = []
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                futures = {pool.submit(work, s): s.source_id for s in selected}
                for fut in as_completed(futures):
                    try:
                        runs.append(fut.result())
                    except Exception as exc:
                        runs.append({"source_id": futures[fut], "status": "failed", "error": str(exc)})
            out = {"workers": max(1, args.workers), "runs": runs}
        elif args.cmd == "seed-existing":
            out = import_seed_jsonl(runner.store, args.file)
            out["stats"] = runner.store.stats()
        else:
            rows = runner.store.conn.execute("""
              SELECT q.id,q.status,q.reason,q.created_at,c.source_id,c.brand,c.product_name,c.source_url,c.confidence
              FROM manual_review_queue q JOIN product_candidates c ON c.candidate_id=q.candidate_id
              WHERE q.status='open' ORDER BY q.created_at LIMIT ?
            """, (args.limit,)).fetchall()
            out = [dict(r) for r in rows]
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    finally:
        runner.close()


if __name__ == "__main__":
    main()
