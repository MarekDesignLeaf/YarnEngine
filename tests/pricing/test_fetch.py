"""Fetching a page whose address a person typed in.

This is one of the few places the app reaches out to an address it did not
choose, so the guard rails matter more than the happy path.
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src.pricing import fetch as fetch_module
from src.pricing.fetch import CannotFetch, check_url, fetch
from src.pricing.shop_page import read_price

PAGE = b"""<html><head><script type="application/ld+json">
{"@type":"Product","name":"Cotton Aran","offers":{"@type":"Offer","price":"4.75",
"priceCurrency":"GBP","availability":"https://schema.org/InStock"}}</script></head>
<body>Cotton Aran 100g</body></html>"""


class _Shop(BaseHTTPRequestHandler):
    def do_GET(self):                                     # noqa: N802
        if self.path == "/gone":
            self.send_response(404); self.end_headers(); return
        if self.path == "/blocked":
            self.send_response(403); self.end_headers(); return
        if self.path == "/image":
            self.send_response(200)
            self.send_header("Content-Type", "image/png"); self.end_headers()
            self.wfile.write(b"\x89PNG"); return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *args):                         # keep the test output quiet
        pass


@pytest.fixture()
def shop(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _Shop)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # The address guard exists to stop a user's URL reaching the machine's own
    # network; a test shop has to live there, so it is lifted here only.
    monkeypatch.setattr(fetch_module, "_check_address", lambda host: None)
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_a_page_is_fetched_and_its_price_read(shop):
    """The two halves together, which is what actually has to work."""
    found = read_price(fetch(f"{shop}/product"), f"{shop}/product")
    assert found["amount"] == 4.75 and found["currency"] == "GBP"
    assert found["availability"] == "in stock"


@pytest.mark.parametrize("path,wanted", [
    ("/gone", "gone from the shop"),
    ("/blocked", "refused the request"),
    ("/image", "not a web page"),
])
def test_what_goes_wrong_is_said_in_words_a_person_can_act_on(shop, path, wanted):
    with pytest.raises(CannotFetch) as caught:
        fetch(shop + path)
    message = str(caught.value)
    assert wanted in message
    assert message[0].isupper() and message.endswith((".", "!"))


@pytest.mark.parametrize("url", [
    "ftp://example.com/p", "file:///etc/passwd", "javascript:alert(1)",
    "not a url", "", "http://",
])
def test_only_a_web_address_is_ever_fetched(url):
    with pytest.raises(CannotFetch):
        check_url(url)


@pytest.mark.parametrize("url", [
    "http://localhost/x", "http://127.0.0.1/x", "http://192.168.1.5/p",
    "http://10.0.0.1/p", "http://169.254.169.254/latest/meta-data/",
])
def test_the_machines_own_network_is_never_fetched(url):
    """A supplier link is typed in by a person, so it could point anywhere —
    including at the server itself."""
    with pytest.raises(CannotFetch) as caught:
        check_url(url)
    assert "private network" in str(caught.value) or "no site" in str(caught.value)


def test_shops_are_not_hammered():
    assert fetch_module.MIN_SECONDS_BETWEEN_CHECKS >= 60
    assert fetch_module.TIMEOUT_SECONDS <= 20
    assert "YarnEngine" in fetch_module.USER_AGENT     # it says who is calling
