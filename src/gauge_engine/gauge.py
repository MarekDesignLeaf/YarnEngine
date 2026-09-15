from dataclasses import dataclass
from enum import Enum
from math import floor, ceil

class RoundingMode(str, Enum):
    NEAREST = "nearest"
    FLOOR = "floor"
    CEIL = "ceil"

@dataclass(frozen=True)
class Gauge:
    stitches: int
    rows: int
    width_mm: float
    height_mm: float

    def __post_init__(self):
        if self.stitches <= 0 or self.rows <= 0:
            raise ValueError("stitches and rows must be > 0")
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValueError("gauge dimensions must be > 0")

    @property
    def wale_spacing_mm(self) -> float:
        """Physical spacing A between adjacent wales."""
        return self.width_mm / self.stitches

    @property
    def course_spacing_mm(self) -> float:
        """Physical spacing B between adjacent courses."""
        return self.height_mm / self.rows

    @property
    def stitches_per_mm(self) -> float:
        return self.stitches / self.width_mm

    @property
    def rows_per_mm(self) -> float:
        return self.rows / self.height_mm

def _round_count(value: float, mode: RoundingMode) -> int:
    if mode == RoundingMode.FLOOR:
        return floor(value)
    if mode == RoundingMode.CEIL:
        return ceil(value)
    # deterministic half-up for positive counts
    return floor(value + 0.5)

@dataclass(frozen=True)
class ProjectGrid:
    requested_width_mm: float
    requested_height_mm: float
    stitches: int
    rows: int
    achieved_width_mm: float
    achieved_height_mm: float

def project_grid(width_mm: float, height_mm: float, gauge: Gauge,
                 rounding: RoundingMode = RoundingMode.NEAREST) -> ProjectGrid:
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("project dimensions must be > 0")
    stitches = max(1, _round_count(width_mm * gauge.stitches_per_mm, rounding))
    rows = max(1, _round_count(height_mm * gauge.rows_per_mm, rounding))
    return ProjectGrid(
        requested_width_mm=width_mm,
        requested_height_mm=height_mm,
        stitches=stitches,
        rows=rows,
        achieved_width_mm=stitches * gauge.wale_spacing_mm,
        achieved_height_mm=rows * gauge.course_spacing_mm,
    )
