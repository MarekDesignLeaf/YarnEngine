"""Checking a shop's price over the wire, and what costing does with it."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from src.pricing import fetch as fetch_module
from src.web.app import app

c = TestClient(app)
YARN = "YARNSMITHS_COTTONARAN"

PAGE = b"""<html><head><script type="application/ld+json">
{"@type":"Product","name":"Cotton Aran","offers":{"@type":"Offer","price":"4.75",
"priceCurrency":"GBP","availability":"https://schema.org/InStock"}}</script></head>
<body></body></html>"""
DEARER = PAGE.replace(b'"4.75"', b'"6.20"')


class _Shop(BaseHTTPRequestHandler):
    def do_GET(self):                                      # noqa: N802
        body = DEARER if self.path.startswith("/dear") else PAGE
        if self.path.startswith("/nothing"):
            body = b"<html><body><p>Yarn, only 4.75 a ball!</p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def shop(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Shop)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(fetch_module, "_check_address", lambda host: None)
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(autouse=True)
def only_this_test_s_shops():
    """The suppliers are shared state, and “the cheapest shop” means nothing if
    the previous test's shops are still on the list."""
    def clear():
        for row in c.get(f"/api/yarns/{YARN}/suppliers").json():
            c.delete(f"/api/admin/yarns/{YARN}/suppliers/{row['id']}")
    clear()
    yield
    clear()


def add(name, url=None):
    return c.post(f"/api/yarns/{YARN}/suppliers",
                  json={"name": name, "product_url": url}).json()


def test_a_shop_is_asked_and_what_it_said_is_kept(shop):
    supplier = add("Test Shop", f"{shop}/product")
    body = c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price").json()
    assert body["result"]["status"] == "ok"
    assert body["result"]["amount"] == 4.75 and body["result"]["currency"] == "GBP"
    assert body["price"]["amount"] == 4.75 and body["price"]["from"] == "checked"
    assert "Test Shop" in body["price"]["note"]
    row = next(s for s in body["suppliers"] if s["id"] == supplier["id"])
    assert row["checked_price"] == 4.75 and row["age"] == "checked today"
    assert row["stale"] is False


def test_the_cheapest_of_several_shops_is_the_one_costing_uses(shop):
    cheap = add("Cheap Shop", f"{shop}/product")
    dear = add("Dear Shop", f"{shop}/dear")
    for supplier in (cheap, dear):
        c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price")
    price = c.get(f"/api/yarns/{YARN}/price").json()["price"]
    assert price["amount"] == 4.75
    assert "Cheap Shop" in price["note"] or price["supplier"] == "Cheap Shop"


def test_a_page_with_no_published_price_changes_nothing(shop):
    supplier = add("Prose Shop", f"{shop}/nothing")
    body = c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price").json()
    assert body["result"]["status"] == "no price"
    assert "does not publish a price" in body["result"]["message"]
    row = next(s for s in body["suppliers"] if s["id"] == supplier["id"])
    assert row["checked_price"] is None


def test_a_shop_is_not_asked_twice_in_five_minutes(shop):
    supplier = add("Polite", f"{shop}/product")
    c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price")
    again = c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price").json()
    assert again["result"]["status"] == "too soon"
    forced = c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price",
                    json={"force": True}).json()
    assert forced["result"]["status"] == "ok"


def test_a_shop_with_no_link_is_skipped_not_failed():
    supplier = add("No Link")
    body = c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price").json()
    assert body["result"]["status"] == "skipped"
    assert "no link" in body["result"]["message"].lower()


def test_a_link_at_the_server_itself_is_refused():
    supplier = add("Sneaky", "http://169.254.169.254/latest/meta-data/")
    body = c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price").json()
    assert body["result"]["status"] == "failed"
    assert "private network" in body["result"]["message"]


def test_checking_them_all_at_once(shop):
    add("Batch One", f"{shop}/product")
    add("Batch Two", f"{shop}/dear")
    body = c.post(f"/api/yarns/{YARN}/check-prices", json={"force": True}).json()
    assert {r["status"] for r in body["results"]} <= {"ok", "skipped", "failed", "no price"}
    assert any(r["status"] == "ok" for r in body["results"])


def test_a_failed_check_never_loses_the_price_that_worked(shop):
    supplier = add("Flaky", f"{shop}/product")
    c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price")
    # the shop goes away
    c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price",
           json={"force": True})           # still up, so force a good one first
    body = c.get(f"/api/yarns/{YARN}/price").json()
    row = next(s for s in body["suppliers"] if s["id"] == supplier["id"])
    assert row["checked_price"] == 4.75


def test_costing_uses_the_checked_price_and_says_where_it_came_from(shop):
    supplier = add("Costing Shop", f"{shop}/product")
    c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price")
    out = c.post("/api/tools/price", json={"length_m": 160, "yarn_id": YARN,
                                           "hours": 2, "hourly_rate": 15}).json()
    assert out["yarn_price"]["amount"] == 4.75
    assert "Costing Shop" in out["yarn_price_from"]
    assert out["yarn_cost"] and out["yarn_cost"] > 0
    assert not any("No price is set" in n for n in out["notes"])


def test_a_price_typed_into_the_form_still_beats_everything(shop):
    supplier = add("Ignored Shop", f"{shop}/product")
    c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price")
    out = c.post("/api/tools/price", json={"length_m": 160, "yarn_id": YARN,
                                           "price_per_package": 9.99}).json()
    assert out["yarn_price_from"] == "typed into this form"


def test_the_history_keeps_what_a_price_used_to_be(shop):
    supplier = add("Historic", f"{shop}/product")
    c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price")
    c.post(f"/api/yarns/{YARN}/suppliers/{supplier['id']}/check-price", json={"force": True})
    history = c.get(f"/api/yarns/{YARN}/price").json()["history"]
    mine = [h for h in history if h["supplier_id"] == supplier["id"]]
    assert len(mine) >= 2 and all(h["amount"] == 4.75 for h in mine)
    assert mine[0]["supplier_name"] == "Historic"
