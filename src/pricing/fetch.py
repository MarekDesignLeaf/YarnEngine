"""Fetching a shop's product page, carefully.

The URL being fetched was typed in by a person, which makes this one of the
few places the app reaches out to an address it did not choose. So: only
http and https, never an address on the machine's own network, a timeout and
a size cap, a user agent that says who is calling, and one page — no crawling
and no following a link into a second request.

Prices are checked when someone asks, not on a schedule, and not twice in the
same few minutes for the same page. A shop that is kind enough to publish its
prices as structured data should not be repaid with traffic.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import requests

USER_AGENT = ("OpenCrochetPro-YarnEngine/1.0 (+https://yarnengine-production.up.railway.app; "
              "price check for a yarn a user has linked)")
TIMEOUT_SECONDS = 12
MAX_BYTES = 3_000_000
# How often the same page may be asked. Nothing here is time-critical: a ball
# of yarn does not change price between one round and the next.
MIN_SECONDS_BETWEEN_CHECKS = 300


class CannotFetch(Exception):
    """Why the page could not be fetched, in words a person can act on."""


def _check_address(host: str) -> None:
    """Refuse anything that resolves onto the machine's own network."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise CannotFetch(f"There is no site at “{host}” — check the address.")
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (address.is_private or address.is_loopback or address.is_link_local
                or address.is_reserved or address.is_multicast):
            raise CannotFetch("That address is on a private network, so it is not a shop page.")


def check_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise CannotFetch("A price can only be read from a web address starting http:// or "
                          "https://.")
    if not parsed.hostname:
        raise CannotFetch("That does not look like a web address.")
    _check_address(parsed.hostname)
    return parsed.geturl()


def fetch(url: str, *, session: requests.Session | None = None) -> str:
    """The page's HTML, or an explanation of why there is none."""
    target = check_url(url)
    caller = session or requests
    try:
        response = caller.get(target, timeout=TIMEOUT_SECONDS, allow_redirects=True,
                              headers={"User-Agent": USER_AGENT,
                                       "Accept": "text/html,application/xhtml+xml",
                                       "Accept-Language": "en-GB,en;q=0.9"},
                              stream=True)
    except requests.Timeout:
        raise CannotFetch("The shop's site did not answer in time. It may be slow right now — "
                          "try again in a minute.")
    except requests.RequestException:
        raise CannotFetch("The shop's site could not be reached.")
    with response:
        if response.status_code == 404:
            raise CannotFetch("That page is gone from the shop — the product may have been "
                              "discontinued or the link may have changed.")
        if response.status_code in (401, 403):
            raise CannotFetch("The shop refused the request. Some sites block anything that is "
                              "not a person with a browser; this one's price will have to be "
                              "typed in.")
        if response.status_code >= 400:
            raise CannotFetch(f"The shop's site answered with an error ({response.status_code}).")
        kind = (response.headers.get("Content-Type") or "").lower()
        if kind and "html" not in kind and "xml" not in kind:
            raise CannotFetch("That link is not a web page, so there is no price on it to read.")
        # Read with a cap rather than trusting the content length: a page that
        # streams forever should not take the app down with it.
        chunks, total = [], 0
        for chunk in response.iter_content(65536):
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_BYTES:
                break
        body = b"".join(chunks)
    encoding = response.encoding or response.apparent_encoding or "utf-8"
    try:
        return body.decode(encoding, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
