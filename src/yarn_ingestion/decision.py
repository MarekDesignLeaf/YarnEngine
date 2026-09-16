from __future__ import annotations

from .models import ProductCandidate, NormalizedYarn


def decide(candidate: ProductCandidate, normalized: NormalizedYarn, auto_import_threshold: float = 0.85) -> tuple[str, str]:
    if candidate.active_evidence.get("discontinued_marker"):
        return "reject", "product page is explicitly marked discontinued or archived"
    if candidate.active_evidence.get("current") is not True:
        return "review", "current catalogue membership was not proven"
    missing = []
    if not normalized.fibre_composition:
        missing.append("composition")
    if not normalized.package_mass_g:
        missing.append("package_mass_g")
    if not normalized.package_length_m:
        missing.append("package_length_m")
    if missing:
        return "review", "missing required core fields: " + ", ".join(missing)
    if candidate.confidence < auto_import_threshold:
        return "review", f"confidence {candidate.confidence:.2f} below auto import threshold {auto_import_threshold:.2f}"
    return "import", "official current catalogue evidence and required technical fields present"
