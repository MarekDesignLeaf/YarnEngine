from __future__ import annotations

import json
from pathlib import Path

from src.import_pipeline.core import canonical_checksum

from .normalizer import compute_tex, parse_composition, cyc_from_weight_class
from .store import IngestionStore, utc_now


def import_seed_jsonl(store: IngestionStore, path: str | Path) -> dict:
    path = Path(path)
    summary = {"rows": 0, "reference_loaded": 0, "imported": 0, "skipped_incomplete": 0, "errors": []}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        summary["rows"] += 1
        try:
            r = json.loads(line)
            store.conn.execute("""
              INSERT OR REPLACE INTO seed_reference_products(product_id,brand,product_name,status,source_url,detail_level,raw_json,loaded_at)
              VALUES(?,?,?,?,?,?,?,?)
            """, (
              r["product_id"], r.get("brand") or "Unknown", r.get("product_name") or r["product_id"],
              r.get("status"), r.get("source_url"), r.get("detail_level"),
              json.dumps(r, ensure_ascii=False, sort_keys=True), utc_now()
            ))
            store.conn.commit()
            summary["reference_loaded"] += 1
            mass = r.get("ball_weight_g")
            length = r.get("length_m")
            fibres = parse_composition(r.get("composition"))
            if not mass or not length or not fibres:
                summary["skipped_incomplete"] += 1
                continue
            needle = r.get("recommended_needle_mm")
            core = {
                "yarn_id": r["product_id"],
                "brand": r.get("brand") or "Unknown",
                "product": r.get("product_name") or r["product_id"],
                "variant": None,
                "cyc_weight": cyc_from_weight_class(r.get("weight_class")),
                "package_mass_g": float(mass),
                "package_length_m": float(length),
                "tex": compute_tex(float(mass), float(length)),
                "nominal_diameter_mm": None,
                "wpi": None,
                "recommended_needle_min_mm": float(needle) if needle not in (None, "") else None,
                "recommended_needle_max_mm": float(needle) if needle not in (None, "") else None,
                "fibre_composition": fibres,
                "source_type": "official_web_seed",
                "source_reference": r.get("source_url"),
                "evidence_level": "manufacturer_official_page" if r.get("detail_level") == "detailed" else "catalogue_listing",
            }
            now = utc_now()
            checksum = canonical_checksum(core)
            store.core.upsert_yarn(core, checksum, now)
            store.core.audit(
                entity_type="yarn", entity_id=core["yarn_id"], version=None,
                source_type=core["source_type"], source_reference=core["source_reference"],
                license_id=None, evidence_level=core["evidence_level"], checksum=checksum, imported_at=now,
            )
            summary["imported"] += 1
        except Exception as exc:
            summary["errors"].append({"line": line_no, "error": str(exc)})
    return summary
