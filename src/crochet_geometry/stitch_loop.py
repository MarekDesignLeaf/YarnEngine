"""Tier-B (uncalibrated) crochet yarn-length baseline.

This is the crochet counterpart of ``src/geometry/ciukas.py`` (the Tier-B
model used for weft knitting). It exists so YarnEngine can return a first
yarn-length estimate for a crochet/amigurumi project even when no physical
calibration evidence has been captured yet for the chosen yarn, hook and
gauge. Calibration remains the accurate path -- this module is only meant
to make the tool usable from day one, with calibration as a supplement that
narrows the estimate once real measurements exist.

Two things are combined, and they do NOT carry the same evidence weight:

1. Single crochet (SC), chain (CH) and slip stitch (SLST) loop geometry is
   anchored to a published, peer-reviewed source:

   J. L. Storck, D. Gerber, L. Steenbock, Y. Kyosev,
   "Topology based modelling of crochet structures",
   Journal of Industrial Textiles, Vol. 52, 2022. DOI: 10.1177/15280837221139250

   That paper models crochet stitches as paths through key points (stitch
   spacing L, stitch height H) and reports that hand-crocheted swatches used
   about (17 +/- 8)% LESS yarn than their key-point path length predicted,
   attributed to tension applied by the crocheter. We reuse that measured
   correction (average factor ~0.83) rather than inventing our own.

2. Every other canonical operation (HDC, DC, TR, DTR, decreases, increases,
   back/front-loop-only, post stitches, puff/popcorn) is NOT individually
   published anywhere we could find. Those are derived from the SC anchor by
   a structural ratio: how many times the working yarn is wrapped around the
   hook and pulled through loops to complete one stitch, per standard Craft
   Yarn Council stitch construction. That wrap count is a mechanical fact
   about how the stitch is worked (e.g. a double crochet always takes yarn
   over + pull-up + two pull-throughs = 4 yarn passes, versus 2 for a single
   crochet) -- it is not a measurement, and is therefore a much weaker basis
   than (1). Results for these operations carry a wider uncertainty band and
   an explicit warning that they are extrapolated, not measured.

Nothing here is a substitute for physical calibration. Every result is
tagged ``status="uncalibrated_geometry_baseline"`` and carries warnings
accordingly; src/production_model callers must prefer an approved
calibration model over this baseline whenever one is available and in
domain.
"""
from dataclasses import dataclass
from math import pi

# Measured correction from Storck et al. 2022: hand-crocheted swatches used
# ~17% (+/- 8 percentage points) less yarn than raw key-point path length.
MEASURED_CORRECTION_FACTOR = 0.83
MEASURED_CORRECTION_HALF_WIDTH = 0.08

# Operations whose loop geometry is anchored to the measured paper above
# (only SC/CH/SLST were actually crocheted and measured by Storck et al.).
MEASURED_ANCHOR_OPERATIONS = frozenset({"CH", "SLST", "SC"})

# Wrap/pull-through count for one instance of each base stitch: how many
# times the working yarn is drawn through a loop on the hook to complete the
# stitch, per standard Craft Yarn Council construction. This is structural
# (definitional to how the stitch is made), not a measured quantity.
_BASE_WRAPS = {
    "CH": 1, "SLST": 1,
    "SC": 2, "SC_BLO": 2, "SC_FLO": 2,
    "HDC": 3, "HDC_BLO": 3,
    "DC": 4, "DC_BLO": 4, "FPDC": 4, "BPDC": 4,
    "TR": 6,
    "DTR": 8,
}
_SC_WRAPS = _BASE_WRAPS["SC"]

def _ntog_wraps(base_wraps: int, n: int) -> float:
    """Wrap count for an N-together decrease of a stitch with `base_wraps`.

    Each additional leg shares one final closing pull-through, so total
    wraps = n * (base_wraps - 1) + 1 (n=1 reduces to base_wraps).
    """
    return n * (base_wraps - 1) + 1

# operation_id -> yarn multiple relative to one single crochet (ratio, not mm).
OPERATION_WRAP_RATIO = {
    "CH": _BASE_WRAPS["CH"] / _SC_WRAPS,
    "SLST": _BASE_WRAPS["SLST"] / _SC_WRAPS,
    "SC": 1.0,
    "SC_BLO": _BASE_WRAPS["SC_BLO"] / _SC_WRAPS,
    "SC_FLO": _BASE_WRAPS["SC_FLO"] / _SC_WRAPS,
    "HDC": _BASE_WRAPS["HDC"] / _SC_WRAPS,
    "HDC_BLO": _BASE_WRAPS["HDC_BLO"] / _SC_WRAPS,
    "DC": _BASE_WRAPS["DC"] / _SC_WRAPS,
    "DC_BLO": _BASE_WRAPS["DC_BLO"] / _SC_WRAPS,
    "FPDC": _BASE_WRAPS["FPDC"] / _SC_WRAPS,
    "BPDC": _BASE_WRAPS["BPDC"] / _SC_WRAPS,
    "TR": _BASE_WRAPS["TR"] / _SC_WRAPS,
    "DTR": _BASE_WRAPS["DTR"] / _SC_WRAPS,
    # increases: two complete stitches worked into a single insertion point.
    "SC_INC": 2 * _BASE_WRAPS["SC"] / _SC_WRAPS,
    "HDC_INC": 2 * _BASE_WRAPS["HDC"] / _SC_WRAPS,
    "DC_INC": 2 * _BASE_WRAPS["DC"] / _SC_WRAPS,
    # decreases: N legs sharing one closing pull-through.
    "SC2TOG": _ntog_wraps(_BASE_WRAPS["SC"], 2) / _SC_WRAPS,
    "SC3TOG": _ntog_wraps(_BASE_WRAPS["SC"], 3) / _SC_WRAPS,
    "HDC2TOG": _ntog_wraps(_BASE_WRAPS["HDC"], 2) / _SC_WRAPS,
    "DC2TOG": _ntog_wraps(_BASE_WRAPS["DC"], 2) / _SC_WRAPS,
    "DC3TOG": _ntog_wraps(_BASE_WRAPS["DC"], 3) / _SC_WRAPS,
}

# Texture stitches (puff/popcorn): construction varies more between designers
# than the stitches above, so these carry a distinctly wider uncertainty.
# PUFF3 = 3x(yo,insert,yo,draw-up-loop) + 1 closing pull-through-all + 1 locking chain.
# POPCORN5 = 5 complete DC into one stitch + 1 closing pull-through.
_HIGH_UNCERTAINTY_WRAPS = {
    "PUFF3": 3 * 2 + 1 + 1,
    "POPCORN5": 5 * _BASE_WRAPS["DC"] + 1,
}
HIGH_UNCERTAINTY_OPERATIONS = frozenset(_HIGH_UNCERTAINTY_WRAPS)
for _op, _w in _HIGH_UNCERTAINTY_WRAPS.items():
    OPERATION_WRAP_RATIO[_op] = _w / _SC_WRAPS


def _positive(name: str, value: float):
    if value <= 0:
        raise ValueError(f"{name} must be > 0")


def sc_loop_key_point_mm(stitch_spacing_mm: float, row_height_mm: float, yarn_diameter_mm: float) -> float:
    """One single-crochet loop path length, before the measured correction.

    Engineering composition in the same style as the knit Tier-B model
    (src/geometry/ciukas.py): a semicircular arc sized by the working yarn's
    own diameter (the wrap around the hook) plus the straight travel to the
    next stitch and up to the next row.
    """
    for n, v in (("stitch_spacing_mm", stitch_spacing_mm), ("row_height_mm", row_height_mm), ("yarn_diameter_mm", yarn_diameter_mm)):
        _positive(n, v)
    arc = pi * yarn_diameter_mm
    travel = 0.5 * stitch_spacing_mm + 0.25 * row_height_mm
    return arc + travel


@dataclass(frozen=True)
class BaselineOperationLength:
    operation_id: str
    length_mm: float
    lower_mm: float
    upper_mm: float
    measured_anchor: bool
    high_uncertainty: bool


def operation_length_mm(operation_id: str, stitch_spacing_mm: float, row_height_mm: float, yarn_diameter_mm: float) -> BaselineOperationLength:
    if operation_id not in OPERATION_WRAP_RATIO:
        raise KeyError(f"no geometry baseline defined for operation {operation_id}")
    sc_mm = sc_loop_key_point_mm(stitch_spacing_mm, row_height_mm, yarn_diameter_mm) * MEASURED_CORRECTION_FACTOR
    ratio = OPERATION_WRAP_RATIO[operation_id]
    length_mm = sc_mm * ratio
    high_uncertainty = operation_id in HIGH_UNCERTAINTY_OPERATIONS
    # SC/CH/SLST inherit the paper's own +/-8 percentage-point correction band.
    # Every other operation is extrapolated via an unmeasured structural ratio,
    # so it gets a wider band; texture stitches (puff/popcorn) wider still.
    if operation_id in MEASURED_ANCHOR_OPERATIONS:
        half_width_frac = MEASURED_CORRECTION_HALF_WIDTH
    elif high_uncertainty:
        half_width_frac = 0.45
    else:
        half_width_frac = 0.25
    return BaselineOperationLength(
        operation_id=operation_id,
        length_mm=length_mm,
        lower_mm=length_mm * (1 - half_width_frac),
        upper_mm=length_mm * (1 + half_width_frac),
        measured_anchor=operation_id in MEASURED_ANCHOR_OPERATIONS,
        high_uncertainty=high_uncertainty,
    )


def program_length_mm(operation_counts: dict, stitch_spacing_mm: float, row_height_mm: float, yarn_diameter_mm: float):
    """Sum baseline length across a canonical operation-count program.

    Returns (core_length_mm, lower_mm, upper_mm, warnings, unsupported_ops).
    Unsupported (unknown) operation ids are skipped and reported so callers
    can decide whether to fail or proceed with a partial, flagged estimate.
    """
    total = 0.0
    lower = 0.0
    upper = 0.0
    warnings = []
    unsupported = []
    used_high_uncertainty = False
    used_extrapolated = False
    for op, n in operation_counts.items():
        n = int(n)
        if n <= 0:
            continue
        if op not in OPERATION_WRAP_RATIO:
            unsupported.append(op)
            continue
        one = operation_length_mm(op, stitch_spacing_mm, row_height_mm, yarn_diameter_mm)
        total += one.length_mm * n
        lower += one.lower_mm * n
        upper += one.upper_mm * n
        if one.high_uncertainty:
            used_high_uncertainty = True
        elif not one.measured_anchor:
            used_extrapolated = True
    warnings.append(
        "uncalibrated geometry baseline: SC/CH/SLST loop length is anchored to a measured "
        "correction from Storck et al. 2022 (Journal of Industrial Textiles, "
        "DOI 10.1177/15280837221139250); other stitches are scaled from it by standard "
        "stitch-construction wrap counts, not independently measured."
    )
    if used_extrapolated:
        warnings.append("this program includes stitch types other than plain SC/CH/SLST; their length is extrapolated by stitch-construction ratio, not independently measured, so treat as order-of-magnitude until calibrated")
    if used_high_uncertainty:
        warnings.append("this program uses texture stitches (puff/popcorn) with high construction variability; uncertainty band widened accordingly")
    if unsupported:
        warnings.append("no geometry baseline for operations: " + ", ".join(sorted(set(unsupported))) + " (excluded from this estimate)")
    return total, lower, upper, tuple(warnings), tuple(unsupported)
