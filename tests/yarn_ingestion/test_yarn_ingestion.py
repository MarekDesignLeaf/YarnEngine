from pathlib import Path

from src.yarn_ingestion.decision import decide
from src.yarn_ingestion.extractor import discover_links, extract_product
from src.yarn_ingestion.models import SourceConfig
from src.yarn_ingestion.normalizer import parse_composition, compute_tex, normalize_candidate
from src.yarn_ingestion.registry import load_registry

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).resolve().parent / "fixtures" / "ingestion"


def source():
    return SourceConfig(
        source_id="SRC_TEST", display_name="Example Yarn", base_url="https://example.test",
        catalogue_urls=("https://example.test/catalogue",), product_url_regex=r"/product/",
        enabled=True, domain_status="verified", robots_policy="ignore",
    )


def test_registry_contains_full_original_seed_list():
    sources = load_registry(ROOT / "data" / "ingestion" / "sources.json")
    assert len(sources) == 232
    assert sum(1 for s in sources if s.enabled) == 5
    assert {s.display_name for s in sources if s.enabled} == {"DROPS", "Scheepjes", "Sirdar", "King Cole", "Malabrigo"}


def test_composition_parser():
    assert parse_composition("65% Wool, 35% Alpaca") == {"Wool": 65.0, "Alpaca": 35.0}
    assert parse_composition("75% Superwash Merino Wool, 25% Nylon") == {"Superwash Merino Wool": 75.0, "Nylon": 25.0}


def test_tex():
    assert round(compute_tex(50, 150), 6) == round(333.3333333333333, 6)


def test_catalogue_discovery():
    html = (FIX / "catalogue.html").read_text()
    products, pages = discover_links("https://example.test/catalogue", html, source())
    assert "https://example.test/product/example-merino-dk/" in products
    assert "https://example.test/catalogue/page/2" in pages


def test_current_product_auto_import_decision():
    html = (FIX / "product_current.html").read_text()
    c = extract_product("https://example.test/product/example-merino-dk/", html, source(), "catalogue_product_link")
    assert c is not None
    n = normalize_candidate(c)
    assert n.brand == "Example Yarn"
    assert n.product == "Example Merino DK"
    assert n.package_mass_g == 100
    assert n.package_length_m == 240
    assert n.fibre_composition == {"Merino Wool": 80.0, "Nylon": 20.0}
    assert n.cyc_weight == 3
    decision, reason = decide(c, n)
    assert decision == "import", reason


def test_discontinued_is_rejected():
    html = (FIX / "product_discontinued.html").read_text()
    c = extract_product("https://example.test/product/old-yarn/", html, source(), "catalogue_product_link")
    assert c is not None
    n = normalize_candidate(c)
    decision, _ = decide(c, n)
    assert decision == "reject"


def test_end_to_end_runner_with_fixture(tmp_path):
    from src.yarn_ingestion.fetcher import FetchResult
    from src.yarn_ingestion.runner import IngestionRunner

    cat = (FIX / "catalogue.html").read_text()
    prod = (FIX / "product_current.html").read_text()

    class FakeFetcher:
        def fetch(self, url, source_cfg):
            if url.endswith("/catalogue"):
                return FetchResult(url, 200, "text/html", cat)
            if "/product/example-merino-dk/" in url:
                return FetchResult(url, 200, "text/html", prod)
            if url.endswith("/catalogue/page/2"):
                return FetchResult(url, 200, "text/html", "<html><body></body></html>")
            raise AssertionError(url)

    db = tmp_path / "ingestion.sqlite"
    r = IngestionRunner(str(db), fetcher=FakeFetcher())
    try:
        s = source()
        r.register_sources([s])
        result = r.crawl_source(s)
        assert result["status"] == "completed"
        assert result["imported_count"] == 1
        assert r.store.stats()["core_yarns"] == 1
        row = r.store.conn.execute("SELECT brand,product,package_mass_g,package_length_m FROM yarns").fetchone()
        assert dict(row) == {"brand":"Example Yarn","product":"Example Merino DK","package_mass_g":100.0,"package_length_m":240.0}
    finally:
        r.close()
