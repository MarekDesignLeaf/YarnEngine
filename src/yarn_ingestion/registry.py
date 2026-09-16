from __future__ import annotations

import json
from pathlib import Path

from .models import SourceConfig


def load_registry(path: str | Path) -> list[SourceConfig]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [SourceConfig(
        source_id=x["source_id"],
        display_name=x["display_name"],
        country=x.get("country"),
        manufacturer_name=x.get("manufacturer_name"),
        base_url=x.get("base_url"),
        catalogue_urls=tuple(x.get("catalogue_urls") or []),
        product_url_regex=x.get("product_url_regex"),
        exclude_url_regex=x.get("exclude_url_regex"),
        adapter=x.get("adapter", "generic"),
        enabled=bool(x.get("enabled", False)),
        domain_status=x.get("domain_status", "needs_verification"),
        max_catalogue_pages=int(x.get("max_catalogue_pages", 30)),
        max_product_pages=int(x.get("max_product_pages", 1500)),
        delay_seconds=float(x.get("delay_seconds", 0.6)),
        robots_policy=x.get("robots_policy", "respect"),
        notes=x.get("notes"),
    ) for x in data]


def by_id(sources: list[SourceConfig]) -> dict[str, SourceConfig]:
    return {s.source_id: s for s in sources}
