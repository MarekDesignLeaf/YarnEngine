from dataclasses import dataclass, asdict
from math import ceil
from src.gauge_engine.gauge import Gauge, RoundingMode, project_grid
from src.calibration.swatch import CoreSwatchCalibration
from src.geometry.ciukas import plain_loop_path_mm
from src.domain.units import mass_g_from_length_m, packages_required

@dataclass(frozen=True)
class CalculationResult:
    tier: str
    core_length_m: float
    allowance_percent: float
    recommended_length_m: float
    mass_g: float | None
    packages: int | None
    stitches: int
    rows: int
    achieved_width_mm: float
    achieved_height_mm: float
    model_status: str
    warnings: tuple[str, ...]

    def to_dict(self):
        d=asdict(self)
        d["warnings"]=list(self.warnings)
        return d

def _finalize(tier, core_length_m, grid, allowance_percent, tex=None, package_length_m=None,
              status="", warnings=()):
    if allowance_percent < 0:
        raise ValueError("allowance_percent must be >= 0")
    recommended=core_length_m*(1+allowance_percent/100.0)
    mass = mass_g_from_length_m(recommended, tex) if tex is not None else None
    packs = packages_required(recommended, package_length_m) if package_length_m is not None else None
    return CalculationResult(
        tier=tier, core_length_m=core_length_m, allowance_percent=allowance_percent,
        recommended_length_m=recommended, mass_g=mass, packages=packs,
        stitches=grid.stitches, rows=grid.rows,
        achieved_width_mm=grid.achieved_width_mm, achieved_height_mm=grid.achieved_height_mm,
        model_status=status, warnings=tuple(warnings)
    )

def calculate_from_swatch(*, width_mm: float, height_mm: float, gauge: Gauge,
                          calibration: CoreSwatchCalibration, allowance_percent: float = 0.0,
                          tex: float | None = None, package_length_m: float | None = None,
                          rounding: RoundingMode = RoundingMode.NEAREST) -> CalculationResult:
    """Tier A. Empirical scaling by stitch-position count at the same gauge/pattern."""
    grid=project_grid(width_mm,height_mm,gauge,rounding)
    core=calibration.predict_core_length_m(grid.stitches,grid.rows)
    return _finalize(
        "A",core,grid,allowance_percent,tex,package_length_m,
        status="empirical_core_swatch",
        warnings=("Valid only when project pattern, yarn behaviour, gauge and knitting conditions are sufficiently equivalent to the calibrated swatch.",)
    )

def calculate_plain_geometry(*, width_mm: float, height_mm: float, gauge: Gauge,
                             yarn_diameter_mm: float, allowance_percent: float = 0.0,
                             tex: float | None = None, package_length_m: float | None = None,
                             rounding: RoundingMode = RoundingMode.NEAREST) -> CalculationResult:
    """Tier B research baseline for plain single-bar weft-knit geometry.

    Not validated for hand knitting. Does not include cast-on, bind-off, tails,
    seams or pattern-specific edge treatments; use allowance or separate components.
    """
    if yarn_diameter_mm <= 0:
        raise ValueError("yarn_diameter_mm must be > 0")
    grid=project_grid(width_mm,height_mm,gauge,rounding)
    loop_mm=plain_loop_path_mm(gauge.wale_spacing_mm,gauge.course_spacing_mm,yarn_diameter_mm)
    core=loop_mm*grid.stitches*grid.rows/1000.0
    return _finalize(
        "B",core,grid,allowance_percent,tex,package_length_m,
        status="research_geometry_unvalidated_for_hand_knitting",
        warnings=(
            "Tier B uses published weft-knit geometry studied on machine-knitted fabrics and must be calibrated before hand-knitting accuracy is claimed.",
            "Yarn diameter is difficult to measure reproducibly for compressible or fuzzy yarn.",
            "Edges, cast-on, bind-off, tails and seams are excluded from the core calculation."
        )
    )
