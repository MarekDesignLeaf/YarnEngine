from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from .models import SourceConfig


@dataclass
class FetchResult:
    url: str
    status_code: int
    content_type: str
    text: str


class PoliteFetcher:
    def __init__(self, user_agent: str = "OpenCrochetPro-YarnEngineCatalogueBot/1.0", timeout: float = 20.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self._last_fetch: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _can_fetch(self, url: str, source: SourceConfig) -> bool:
        if source.robots_policy == "ignore":
            return True
        p = urlparse(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(origin + "/robots.txt")
            try:
                rp.read()
                self._robots[origin] = rp
            except Exception:
                # Fail closed for production ingestion. Source can explicitly override.
                self._robots[origin] = None
        rp = self._robots[origin]
        return bool(rp and rp.can_fetch(self.user_agent, url))

    def fetch(self, url: str, source: SourceConfig) -> FetchResult:
        if not self._can_fetch(url, source):
            raise PermissionError(f"robots policy does not permit fetch or robots.txt could not be verified: {url}")
        host = urlparse(url).netloc
        last = self._last_fetch.get(host, 0.0)
        wait = source.delay_seconds - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
        resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        self._last_fetch[host] = time.monotonic()
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "text/html" not in ctype and "application/xhtml" not in ctype and "xml" not in ctype:
            raise ValueError(f"unsupported content type {ctype!r} for {url}")
        return FetchResult(resp.url, resp.status_code, ctype, resp.text)
