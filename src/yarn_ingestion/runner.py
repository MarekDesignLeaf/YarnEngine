from __future__ import annotations

from collections import deque
import traceback

from src.storage.sqlite_store import SQLiteStore

from .decision import decide
from .extractor import discover_links, extract_product
from .fetcher import PoliteFetcher
from .models import SourceConfig
from .normalizer import normalize_candidate
from .store import IngestionStore


class IngestionRunner:
    def __init__(self, db_path: str, fetcher: PoliteFetcher | None = None, auto_import_threshold: float = 0.85):
        self.core = SQLiteStore(db_path)
        self.store = IngestionStore(self.core)
        self.fetcher = fetcher or PoliteFetcher()
        self.auto_import_threshold = auto_import_threshold

    def close(self):
        self.core.close()

    def register_sources(self, sources: list[SourceConfig]):
        for source in sources:
            self.store.upsert_source(source)

    def crawl_source(self, source: SourceConfig) -> dict:
        if not source.enabled:
            return {"source_id": source.source_id, "status": "skipped", "reason": "source disabled"}
        if source.domain_status != "verified" or not source.catalogue_urls:
            return {"source_id": source.source_id, "status": "skipped", "reason": "source domain/catalogue not verified"}

        run_id = self.store.start_run(source.source_id)
        summary = {
            "source_id": source.source_id, "run_id": run_id, "pages_fetched": 0, "candidates_found": 0,
            "imported_count": 0, "review_count": 0, "rejected_count": 0, "error_count": 0, "errors": [],
        }
        try:
            product_links: set[str] = set()
            queue = deque((url, "catalogue_seed") for url in source.catalogue_urls)
            seen_catalogues: set[str] = set()
            while queue and len(seen_catalogues) < source.max_catalogue_pages:
                url, via = queue.popleft()
                if url in seen_catalogues:
                    continue
                seen_catalogues.add(url)
                try:
                    page = self.fetcher.fetch(url, source)
                    summary["pages_fetched"] += 1
                    self.store.record_page(run_id, source.source_id, page.url, via, page.status_code, page.content_type, page.text)
                    products, next_pages = discover_links(page.url, page.text, source)
                    product_links.update(products)
                    for nxt in next_pages:
                        if nxt not in seen_catalogues:
                            queue.append((nxt, "catalogue_pagination"))
                except Exception as exc:
                    summary["error_count"] += 1
                    summary["errors"].append({"url": url, "error": str(exc)})

            for idx, url in enumerate(sorted(product_links)):
                if idx >= source.max_product_pages:
                    break
                try:
                    page = self.fetcher.fetch(url, source)
                    summary["pages_fetched"] += 1
                    self.store.record_page(run_id, source.source_id, page.url, "catalogue_product_link", page.status_code, page.content_type, page.text)
                    candidate = extract_product(page.url, page.text, source, "catalogue_product_link")
                    if not candidate:
                        summary["error_count"] += 1
                        summary["errors"].append({"url": url, "error": "could not identify product name"})
                        continue
                    summary["candidates_found"] += 1
                    normalized = normalize_candidate(candidate)
                    decision, reason = decide(candidate, normalized, self.auto_import_threshold)
                    self.store.save_candidate(run_id, candidate, normalized, decision, reason)
                    if decision == "import":
                        self.store.import_to_core(normalized)
                        summary["imported_count"] += 1
                    elif decision == "review":
                        summary["review_count"] += 1
                    else:
                        summary["rejected_count"] += 1
                except Exception as exc:
                    summary["error_count"] += 1
                    summary["errors"].append({"url": url, "error": str(exc)})

            status = "completed" if summary["error_count"] == 0 else "completed_with_errors"
            self.store.finish_run(run_id, status, summary)
            summary["status"] = status
            return summary
        except Exception as exc:
            summary["error_count"] += 1
            summary["errors"].append({"error": str(exc), "traceback": traceback.format_exc(limit=5)})
            self.store.finish_run(run_id, "failed", summary)
            summary["status"] = "failed"
            return summary
