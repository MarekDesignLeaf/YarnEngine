from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    display_name: str
    country: str | None = None
    manufacturer_name: str | None = None
    base_url: str | None = None
    catalogue_urls: tuple[str, ...] = ()
    product_url_regex: str | None = None
    exclude_url_regex: str | None = None
    adapter: str = "generic"
    enabled: bool = False
    domain_status: str = "needs_verification"
    max_catalogue_pages: int = 30
    max_product_pages: int = 1500
    delay_seconds: float = 0.6
    robots_policy: str = "respect"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["catalogue_urls"] = list(self.catalogue_urls)
        return d


@dataclass
class ProductCandidate:
    source_id: str
    brand: str
    product_name: str
    source_url: str
    discovered_via: str
    raw: dict[str, Any] = field(default_factory=dict)
    active_evidence: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedYarn:
    yarn_id: str
    brand: str
    product: str
    variant: str | None
    cyc_weight: int | None
    package_mass_g: float | None
    package_length_m: float | None
    tex: float | None
    nominal_diameter_mm: float | None
    wpi: float | None
    recommended_needle_min_mm: float | None
    recommended_needle_max_mm: float | None
    fibre_composition: dict[str, float]
    source_type: str
    source_reference: str
    evidence_level: str
    status: str = "current"
    raw_weight_class: str | None = None
    gauge_sts_10cm: float | None = None
    gauge_rows_10cm: float | None = None
    sku: str | None = None
    gtin: str | None = None
    colour_count: int | None = None
    care: str | None = None
    certification: str | None = None
    made_in: str | None = None
    raw_material_origin: str | None = None

    @property
    def importable_to_core(self) -> bool:
        return bool(
            self.status == "current"
            and self.package_mass_g
            and self.package_mass_g > 0
            and self.package_length_m
            and self.package_length_m > 0
            and self.fibre_composition
        )

    def core_dict(self) -> dict[str, Any]:
        if not self.importable_to_core:
            raise ValueError("record is not complete enough for core yarn import")
        return {
            "yarn_id": self.yarn_id,
            "brand": self.brand,
            "product": self.product,
            "variant": self.variant,
            "cyc_weight": self.cyc_weight,
            "package_mass_g": self.package_mass_g,
            "package_length_m": self.package_length_m,
            "tex": self.tex,
            "nominal_diameter_mm": self.nominal_diameter_mm,
            "wpi": self.wpi,
            "recommended_needle_min_mm": self.recommended_needle_min_mm,
            "recommended_needle_max_mm": self.recommended_needle_max_mm,
            "fibre_composition": self.fibre_composition,
            "source_type": self.source_type,
            "source_reference": self.source_reference,
            "evidence_level": self.evidence_level,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
