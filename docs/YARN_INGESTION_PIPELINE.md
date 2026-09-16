# Automated yarn-catalogue ingestion

`src/yarn_ingestion/` is a provenance-first pipeline for growing the yarn
catalogue from manufacturer websites, plus the existing v0.5 reference
spreadsheet. It is additive: it does not replace `src.storage.sqlite_store`,
provenance audit, quarantine, or the existing yarn model — it writes through
the same `SQLiteStore.upsert_yarn()` / `.audit()` calls as everything else.

## What's actually in the live catalogue today

The v0.5 reference dataset (`data/ingestion/seed_current_products_v0_5.jsonl`,
296 products across DROPS, Scheepjes, Sirdar, King Cole and Malabrigo) has
101 products with complete technical data (mass, length, fibre composition).
Those 101 were converted to `data/yarns/YRN000xx.json` files in the same
format as every other yarn in the library, so they go through the normal
`bulk_import_yarns` validation and ship on every deploy exactly like the
hand-curated yarns already there. The other 195 rows are missing a required
field (usually mass or length) and are kept as reference-only data in the
`seed_reference_products` table for later completion — nothing is invented
to fill the gap.

**No live web crawling has been run.** The crawler (`fetcher.py` /
`extractor.py`) is implemented, tested against local HTML fixtures, and
respects `robots.txt` by default (fails closed if it can't be checked), but
it has not been pointed at any real manufacturer site yet. `data/ingestion/sources.json`
lists 232 manufacturers/brands; only 5 (DROPS, Scheepjes, Sirdar, King Cole,
Malabrigo) are marked `domain_status=verified` with a real catalogue URL —
the rest are intentionally disabled (`needs_verification`) until someone
confirms their real current-catalogue domain. No domain is guessed.

## Where things live in the running app

- Source registry + reference table are synced into the *same*
  `data/db/web_app.sqlite` the rest of the app uses (`_sync_ingestion_registry()`
  in `src/web/app.py`, run at startup, upsert-based like the rest of the
  bootstrap).
- Read-only status: `GET /api/admin/ingestion/stats`, `GET /api/admin/ingestion/review`
  (admin-only), and an "Yarn data ingestion" card on the admin page.
- Command-line tool: `python run_ingestion.py --db data/db/web_app.sqlite <command>`
  (`init`, `status`, `sources`, `crawl-source <id>`, `crawl-all`, `seed-existing`,
  `review`) — note the `--db` path matches the real app database, not the
  `data/db/yarn_engine.sqlite` default baked into the CLI.

## Running a real crawl

`crawl-source` / `crawl-all` make real HTTP requests to manufacturer sites
(politely: robots.txt-respecting, rate-limited per domain). That hasn't been
done as part of this integration — it's a deliberate, separate step for
whenever it's actually wanted, since it means the app making outbound
requests to five real commercial websites at volume. Verifying the other 227
sources' real domains is manual, one at a time, before they can be enabled.

## Dependencies

`requests`, `beautifulsoup4`, `lxml` are now part of `requirements.txt` /
`requirements-web.txt` (pinned) since the web app imports the ingestion
package at startup to sync the registry.
