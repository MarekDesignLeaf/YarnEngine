from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)


def test_ingestion_stats_reports_registered_sources_and_web_ingested_yarns():
    r = client.get('/api/admin/ingestion/stats')
    assert r.status_code == 200
    body = r.json()
    assert body['sources'] == 232
    assert body['sources_verified'] == 5
    assert body['sources_needing_verification'] == 227
    assert body['seed_reference_products'] == 296
    # The 101 complete v0.5 records were bundled into data/yarns/*.json and are
    # already part of the live catalogue via the normal bootstrap import.
    assert body['web_ingested_yarns'] == 101


def test_ingestion_review_queue_is_empty_until_a_crawl_runs():
    r = client.get('/api/admin/ingestion/review')
    assert r.status_code == 200
    assert r.json() == []
