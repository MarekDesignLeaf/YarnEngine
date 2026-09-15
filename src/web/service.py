import json
from pathlib import Path
from dataclasses import asdict

from src.storage.sqlite_store import SQLiteStore
from src.pattern_engine.loader import load_pattern_dict
from src.pattern_engine.registry import load_operation_registry
from src.gauge_engine.gauge import Gauge
from src.project_geometry.model import EdgeZone, PartialRepeatMode
from src.consumption.project_adapter import create_project_pattern_plan
from src.calibration.swatch import CoreSwatchCalibration
from src.consumption.engine import calculate_from_swatch, calculate_plain_geometry
from src.library.compatibility import assess_yarn_for_gauge
from src.production_model.runtime import calculate_with_production_model


class WebService:
    def __init__(self, root: Path, db_path: Path, model_registry=None):
        self.root = root
        self.db_path = db_path
        self.model_registry = model_registry
        self.operations = load_operation_registry(root / "data/stitches/operations.seed.json")

    def _store(self):
        return SQLiteStore(self.db_path)

    def patterns(self):
        store = self._store()
        try:
            rows = store.conn.execute(
                "SELECT pattern_id,version,name,family_id,difficulty,tags_json,techniques_json "
                "FROM patterns WHERE active=1 ORDER BY family_id,name,version"
            ).fetchall()
            return [
                {
                    "pattern_id": r["pattern_id"],
                    "version": r["version"],
                    "name": r["name"],
                    "family_id": r["family_id"],
                    "difficulty": r["difficulty"],
                    "tags": json.loads(r["tags_json"]),
                    "techniques": json.loads(r["techniques_json"]),
                }
                for r in rows
            ]
        finally:
            store.close()

    def yarns(self):
        store = self._store()
        try:
            rows = store.conn.execute(
                "SELECT yarn_id,brand,product,variant,cyc_weight,package_mass_g,package_length_m,tex,"
                "nominal_diameter_mm,wpi,recommended_needle_min_mm,recommended_needle_max_mm,"
                "fibre_json,source_type,evidence_level FROM yarns ORDER BY brand,product"
            ).fetchall()
            return [
                {
                    "yarn_id": r["yarn_id"],
                    "brand": r["brand"],
                    "product": r["product"],
                    "variant": r["variant"],
                    "cyc_weight": r["cyc_weight"],
                    "package_mass_g": r["package_mass_g"],
                    "package_length_m": r["package_length_m"],
                    "tex": r["tex"],
                    "nominal_diameter_mm": r["nominal_diameter_mm"],
                    "wpi": r["wpi"],
                    "recommended_needle_min_mm": r["recommended_needle_min_mm"],
                    "recommended_needle_max_mm": r["recommended_needle_max_mm"],
                    "fibre_composition": json.loads(r["fibre_json"]),
                    "source_type": r["source_type"],
                    "evidence_level": r["evidence_level"],
                }
                for r in rows
            ]
        finally:
            store.close()

    def _pattern(self, pattern_id, version):
        store = self._store()
        try:
            r = store.conn.execute(
                "SELECT pattern_json,name,family_id FROM patterns WHERE pattern_id=? AND version=?",
                (pattern_id, version),
            ).fetchone()
            if r is None:
                raise KeyError(f"pattern {pattern_id} {version} not found")
            return load_pattern_dict(json.loads(r["pattern_json"])), r["name"], r["family_id"]
        finally:
            store.close()

    def _yarn(self, yarn_id):
        if not yarn_id:
            return None
        store = self._store()
        try:
            r = store.conn.execute("SELECT * FROM yarns WHERE yarn_id=?", (yarn_id,)).fetchone()
            return dict(r) if r is not None else None
        finally:
            store.close()

    def calculate(self, req):
        pattern, pattern_name, family_id = self._pattern(req.pattern_id, req.pattern_version)
        yarn = self._yarn(req.yarn_id)
        if req.yarn_id and yarn is None:
            raise KeyError(f"yarn {req.yarn_id} not found")

        if req.calculation_mode == "geometry" and req.pattern_id != "STOCKINETTE":
            raise ValueError("research geometry mode is currently restricted to STOCKINETTE")

        gauge = Gauge(
            req.gauge_stitches_per_10cm,
            req.gauge_rows_per_10cm,
            100.0,
            100.0,
        )
        edges = EdgeZone(
            req.edges.left_stitches,
            req.edges.right_stitches,
            req.edges.left_operation,
            req.edges.right_operation,
        )
        plan = create_project_pattern_plan(
            width_mm=req.width_cm * 10.0,
            height_mm=req.height_cm * 10.0,
            gauge=gauge,
            pattern=pattern,
            operations=self.operations,
            edges=edges,
            partial_mode=PartialRepeatMode(req.partial_repeat_mode),
        )

        tex = yarn.get("tex") if yarn else None
        package_length = yarn.get("package_length_m") if yarn else None
        warnings = []

        if req.calculation_mode == "calibrated":
            if self.model_registry is None:
                raise ValueError("production model registry unavailable")
            production=self.model_registry.production()
            if production is None:
                raise ValueError("no approved production calibration model")
            diameter=(yarn.get("nominal_diameter_mm") if yarn else None) or req.yarn_diameter_mm
            if diameter is None:
                raise ValueError("calibrated mode requires yarn nominal diameter or explicit yarn_diameter_mm")
            calc,pred=calculate_with_production_model(
                record=production,operation_counts=plan.operation_counts,gauge=gauge,
                width_mm=req.width_cm*10.0,height_mm=req.height_cm*10.0,yarn_diameter_mm=diameter,
                allowance_percent=req.allowance_percent,tex=tex,package_length_m=package_length,domain_policy=req.domain_policy)
            confidence={
                "level":"production_model_in_domain" if pred.in_domain else "production_model_out_of_domain",
                "label":"Tier B approved operation model",
                "explanation":"Uses an explicitly approved production calibration model. Domain checks are applied at runtime.",
            }
            warnings.extend(pred.warnings)
        elif req.calculation_mode == "swatch":
            calibration = CoreSwatchCalibration(
                req.swatch.stitches,
                req.swatch.rows,
                req.swatch.yarn_length_m,
            )
            calc = calculate_from_swatch(
                width_mm=req.width_cm * 10.0,
                height_mm=req.height_cm * 10.0,
                gauge=gauge,
                calibration=calibration,
                allowance_percent=req.allowance_percent,
                tex=tex,
                package_length_m=package_length,
            )
            confidence = {
                "level": "calibrated",
                "label": "Measured swatch",
                "explanation": "Uses measured yarn consumption from an equivalent swatch. Accuracy still depends on pattern, yarn, gauge and knitting conditions remaining equivalent.",
            }
        else:
            calc = calculate_plain_geometry(
                width_mm=req.width_cm * 10.0,
                height_mm=req.height_cm * 10.0,
                gauge=gauge,
                yarn_diameter_mm=req.yarn_diameter_mm,
                allowance_percent=req.allowance_percent,
                tex=tex,
                package_length_m=package_length,
            )
            confidence = {
                "level": "research",
                "label": "Research baseline",
                "explanation": "Published weft-knit geometry is used as an unvalidated baseline for hand knitting. A measured swatch is preferred.",
            }

        warnings.extend(calc.warnings)
        compatibility = None
        if yarn:
            # Lightweight object with the attributes expected by M4 compatibility screening.
            class Y: pass
            y = Y()
            for k, v in yarn.items(): setattr(y, k, v)
            comp = assess_yarn_for_gauge(y, req.gauge_stitches_per_10cm)
            compatibility = asdict(comp)
            warnings.extend(comp.warnings)

        return {
            "pattern": {"id": req.pattern_id, "version": req.pattern_version, "name": pattern_name, "family": family_id},
            "yarn": None if yarn is None else {
                "id": yarn["yarn_id"], "brand": yarn["brand"], "product": yarn["product"],
                "package_length_m": yarn["package_length_m"], "package_mass_g": yarn["package_mass_g"],
                "tex": yarn["tex"], "evidence_level": yarn["evidence_level"], "source_type": yarn["source_type"],
            },
            "project": {
                "requested_width_cm": req.width_cm,
                "requested_height_cm": req.height_cm,
                "stitches": plan.stitches,
                "rows": plan.rows,
                "achieved_width_cm": plan.achieved_width_mm / 10.0,
                "achieved_height_cm": plan.achieved_height_mm / 10.0,
                "horizontal_layout": asdict(plan.horizontal_layout),
                "vertical_layout": asdict(plan.vertical_layout),
                "operation_counts": plan.operation_counts,
            },
            "consumption": calc.to_dict(),
            "confidence": confidence,
            "compatibility": compatibility,
            "warnings": list(dict.fromkeys(warnings)),
            "audit": {
                "calculation_mode": req.calculation_mode,
                "domain_policy": req.domain_policy,
                "prediction_tier": ("A" if req.calculation_mode=="swatch" else "B" if req.calculation_mode=="calibrated" else "research_geometry"),
                "gauge": {
                    "stitches_per_10cm": req.gauge_stitches_per_10cm,
                    "rows_per_10cm": req.gauge_rows_per_10cm,
                    "wale_spacing_mm": gauge.wale_spacing_mm,
                    "course_spacing_mm": gauge.course_spacing_mm,
                },
                "allowance_percent": req.allowance_percent,
                "partial_repeat_mode": req.partial_repeat_mode,
                "production_model": (
                    {"model_id": self.model_registry.production()["model_id"],
                     "stage": self.model_registry.production()["stage"],
                     "created_at": self.model_registry.production()["created_at"],
                      "promoted_at": self.model_registry.production()["promoted_at"],
                     "model_schema_version": self.model_registry.production().get("model_schema_version"),
                     "feature_spec_version": self.model_registry.production().get("feature_spec_version")}
                    if req.calculation_mode=="calibrated" and self.model_registry and self.model_registry.production()
                    else None
                ),
            },
        }
