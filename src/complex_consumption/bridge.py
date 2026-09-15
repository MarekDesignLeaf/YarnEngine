from src.production_model.runtime import calculate_with_production_model
from src.consumption.engine import _finalize
from src.calibration.predict import Prediction
from src.gauge_engine.gauge import project_grid
from src.crochet_geometry.stitch_loop import program_length_mm, estimate_hook_mm

UNCALIBRATED_BASELINE_MODEL_ID = "uncalibrated_geometry_baseline_v1"


def calculate_uncalibrated_baseline(*, operation_counts, gauge, yarn_diameter_mm, hook_mm=None, cyc_weight=None,
                                     allowance_percent=0.0, tex=None, package_length_m=None):
    """Tier-B crochet fallback used when no approved calibration model exists yet.

    Calibration remains the accurate path (Tier A, via calculate_with_production_model)
    and is preferred whenever available; this exists only so a first estimate can be
    returned from the start. See src/crochet_geometry/stitch_loop.py for the geometry
    and its sourcing/uncertainty.
    """
    hook_warn = ()
    if not hook_mm:
        hook_mm = estimate_hook_mm(yarn_diameter_mm, cyc_weight)
        hook_warn = (f"hook size not given; assumed {hook_mm:.2f} mm from the yarn weight/diameter",)
    core_mm, lower_mm, upper_mm, warnings, unsupported = program_length_mm(operation_counts, hook_mm, yarn_diameter_mm)
    warnings = hook_warn + warnings
    if core_mm <= 0:
        raise ValueError("no crochet operations with a geometry baseline in this program")
    core_m = core_mm / 1000.0
    half_width_m = max(core_m - lower_mm / 1000.0, upper_mm / 1000.0 - core_m)
    pred = Prediction(
        estimate_m=core_m,
        lower_95_m=max(0.0, core_m - half_width_m),
        upper_95_m=core_m + half_width_m,
        in_domain=False,
        warnings=warnings,
    )
    grid = project_grid(100.0, 100.0, gauge)
    calc = _finalize(
        "B", core_m, grid, allowance_percent, tex, package_length_m,
        status="uncalibrated_geometry_baseline",
        warnings=warnings + (
            "no approved crochet calibration model was available; this estimate uses the "
            "uncalibrated geometry baseline and should be treated as a rough starting figure "
            "until a real calibration measurement is captured for this yarn/hook/gauge",
        ),
    )
    return calc, pred, tuple(unsupported)


def calculate_operation_program(*, record, operation_counts, gauge, yarn_diameter_mm, allowance_percent=0.0,
                                tex=None, package_length_m=None, domain_policy="strict", source="operation_program",
                                hook_mm=None, cyc_weight=None):
    """Consumption bridge for shaped, branch and amigurumi programs.
    Uses actual aggregated canonical operation counts instead of rectangular repeat expansion.

    Prefers an approved calibration model (record) when one is available and in domain.
    Falls back to the uncalibrated geometry baseline otherwise, so a project always gets
    a first estimate; calibration is a supplement that replaces/narrows it, not a gate.
    """
    if not operation_counts or sum(int(v) for v in operation_counts.values())<=0:
        raise ValueError("operation program contains no yarn-consuming operations")
    # Width/height are not used to derive counts here. They are retained as a neutral grid carrier
    # for the legacy result envelope; operation counts are authoritative.
    if record is not None:
        calc,pred=calculate_with_production_model(
            record=record,operation_counts=operation_counts,gauge=gauge,
            width_mm=100.0,height_mm=100.0,yarn_diameter_mm=yarn_diameter_mm,
            allowance_percent=allowance_percent,tex=tex,package_length_m=package_length_m,
            domain_policy=domain_policy)
        return calc,pred,{"source":source,"operation_counts":dict(operation_counts),
                          "count_basis":"executed canonical operation program",
                          "rectangular_area_used_for_operation_counts":False,
                          "estimate_basis":"calibrated_production_model"}
    calc,pred,unsupported=calculate_uncalibrated_baseline(
        operation_counts=operation_counts,gauge=gauge,yarn_diameter_mm=yarn_diameter_mm,hook_mm=hook_mm,cyc_weight=cyc_weight,
        allowance_percent=allowance_percent,tex=tex,package_length_m=package_length_m)
    return calc,pred,{"source":source,"operation_counts":dict(operation_counts),
                      "count_basis":"executed canonical operation program",
                      "rectangular_area_used_for_operation_counts":False,
                      "estimate_basis":"uncalibrated_geometry_baseline",
                      "unsupported_operations":list(unsupported)}
