from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class CalibrationSample:
    calibration_id: str
    pattern_id: str
    operation_counts: Mapping[str,int]
    yarn_length_m: float
    wale_spacing_mm: float
    course_spacing_mm: float
    yarn_diameter_mm: float | None = None
    tex: float | None = None

    def __post_init__(self):
        if not self.calibration_id:
            raise ValueError("calibration_id required")
        if self.yarn_length_m <= 0:
            raise ValueError("yarn_length_m must be > 0")
        if self.wale_spacing_mm <= 0 or self.course_spacing_mm <= 0:
            raise ValueError("gauge spacings must be > 0")
        if not self.operation_counts or sum(self.operation_counts.values()) <= 0:
            raise ValueError("operation_counts must be non-empty and positive")
        if any(v < 0 for v in self.operation_counts.values()):
            raise ValueError("operation counts cannot be negative")
        if self.yarn_diameter_mm is not None and self.yarn_diameter_mm <= 0:
            raise ValueError("yarn diameter must be > 0")
        if self.tex is not None and self.tex <= 0:
            raise ValueError("tex must be > 0")
