from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True)
class MeasurementEvidence:
    operator_id: str
    date_iso: str
    method: str
    instrument_id: str | None = None
    photo_reference: str | None = None
    notes: str | None = None

@dataclass(frozen=True)
class RealSwatchRecord:
    record_id: str
    replicate_group_id: str
    knitter_id: str
    pattern_id: str
    yarn_id: str
    needle_mm: float
    gauge_stitches: int
    gauge_rows: int
    gauge_width_mm: float
    gauge_height_mm: float
    operation_counts: Mapping[str,int]
    yarn_length_m: float
    yarn_mass_g: float | None
    tex: float | None
    yarn_diameter_mm: float | None
    condition: str
    evidence: MeasurementEvidence

    def __post_init__(self):
        if not self.record_id or not self.replicate_group_id:
            raise ValueError("record_id and replicate_group_id required")
        if not self.knitter_id or not self.pattern_id or not self.yarn_id:
            raise ValueError("knitter_id, pattern_id, yarn_id required")
        if self.needle_mm <= 0:
            raise ValueError("needle_mm must be > 0")
        if min(self.gauge_stitches,self.gauge_rows) <= 0:
            raise ValueError("gauge counts must be > 0")
        if min(self.gauge_width_mm,self.gauge_height_mm) <= 0:
            raise ValueError("gauge dimensions must be > 0")
        if self.yarn_length_m <= 0:
            raise ValueError("yarn_length_m must be > 0")
        if not self.operation_counts or any(v<0 for v in self.operation_counts.values()):
            raise ValueError("operation_counts invalid")
        if self.condition not in {"unblocked","blocked","washed","relaxed","unknown"}:
            raise ValueError("invalid condition")

    @property
    def wale_spacing_mm(self):
        return self.gauge_width_mm/self.gauge_stitches

    @property
    def course_spacing_mm(self):
        return self.gauge_height_mm/self.gauge_rows
