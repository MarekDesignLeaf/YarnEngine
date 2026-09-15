"""Tier-B (uncalibrated) crochet yarn-length baseline.

This is the crochet counterpart of ``src/geometry/ciukas.py`` (the Tier-B
model used for weft knitting). It lets YarnEngine return a first yarn-length
estimate for a crochet/amigurumi project before any physical calibration has
been captured for the chosen yarn, hook and tension. Calibration remains the
accurate path -- a measured swatch or an approved calibration model replaces
this baseline whenever one exists.

Model
-----
Every canonical crochet operation is worked as a fixed number of yarn passes
(yarn-over / pull-through motions), per standard Craft Yarn Council stitch
construction. Each pass forms one loop around the hook shank together with the
working yarn, so the yarn it consumes is close to one loop circumference:

    length_per_stitch = wraps(op) * TENSION * pi * (hook_mm + yarn_diameter_mm)

Evidence
--------
* Wrap counts are structural facts about how each stitch is made (SC = 2,
  HDC = 3, DC = 4, TR = 6, DTR = 8; decreases share one closing pull-through;
  increases are two complete stitches). The measured ratios in the swatch
  experiment below (HDC/SC = 1.48, DC/SC = 2.00) match these counts (1.5, 2.0).
* The per-wrap loop length was checked against a published swatch experiment
  (Interweave, "Does Crochet Use More Yarn? A Yarn Usage Experiment": Universal
  Yarn Deluxe Chunky, 6 mm hook, 20 x 20 stitch swatches weighing 19 g for SC,
  28 g for HDC and 38 g for DC). Those swatches work out to 26.2, 25.7 and
  26.1 mm of yarn per pass respectively -- almost constant -- versus a
  geometric loop circumference pi*(6 + 3.5) = 29.8 mm, i.e. a tension factor
  of about 0.87.
* Storck et al. 2022 ("Topology based modelling of crochet structures",
  Journal of Industrial Textiles, DOI 10.1177/15280837221139250) independently
  report hand-crocheted swatches using (17 +/- 8)% less yarn than a pure
  key-point path length, i.e. a factor of about 0.83. TENSION below sits
  between the two observations.

Both sources cover only a handful of stitches with one yarn each, so this is a
baseline, not a measurement of *your* yarn and tension. Results are tagged
``status="uncalibrated_geometry_baseline"`` and carry warnings; texture
stitches (puff/popcorn) and anything not covered by the experiment carry a
wider uncertainty band.
"""
from dataclasses import dataclass
from math import pi

TENSION_FACTOR = 0.85          # measured/geometric loop length, see module docstring
MEASURED_HALF_WIDTH = 0.15     # SC/HDC/DC: checked against a published swatch experiment
EXTRAPOLATED_HALF_WIDTH = 0.25 # other plain stitches: wrap-count scaling only
TEXTURE_HALF_WIDTH = 0.45      # puff/popcorn: construction varies between designers

# Operations whose per-stitch length was checked against measured swatches.
MEASURED_ANCHOR_OPERATIONS = frozenset({"SC", "HDC", "DC"})

# Yarn passes for one instance of each base stitch (structural, not measured).
_BASE_WRAPS = {
    "CH": 1, "SLST": 1,
    "SC": 2, "SC_BLO": 2, "SC_FLO": 2,
    "HDC": 3, "HDC_BLO": 3,
    "DC": 4, "DC_BLO": 4, "FPDC": 4, "BPDC": 4,
    "TR": 6,
    "DTR": 8,
}

def _ntog_wraps(base_wraps: int, n: int) -> float:
    """N-together decrease: each leg repeats all but the shared closing pull-through."""
    return n * (base_wraps - 1) + 1

OPERATION_WRAPS = dict(_BASE_WRAPS)
OPERATION_WRAPS.update({
    "SC_INC": 2 * _BASE_WRAPS["SC"], "HDC_INC": 2 * _BASE_WRAPS["HDC"], "DC_INC": 2 * _BASE_WRAPS["DC"],
    "SC2TOG": _ntog_wraps(_BASE_WRAPS["SC"], 2), "SC3TOG": _ntog_wraps(_BASE_WRAPS["SC"], 3),
    "HDC2TOG": _ntog_wraps(_BASE_WRAPS["HDC"], 2),
    "DC2TOG": _ntog_wraps(_BASE_WRAPS["DC"], 2), "DC3TOG": _ntog_wraps(_BASE_WRAPS["DC"], 3),
    # PUFF3 = 3x(yo, insert, yo, draw up) + pull through all + locking chain.
    "PUFF3": 3 * 2 + 1 + 1,
    # POPCORN5 = 5 complete DC into one stitch + 1 closing pull-through.
    "POPCORN5": 5 * _BASE_WRAPS["DC"] + 1,
})
HIGH_UNCERTAINTY_OPERATIONS = frozenset({"PUFF3", "POPCORN5"})
# Kept for callers that reason in multiples of a single crochet.
OPERATION_WRAP_RATIO = {op: w / _BASE_WRAPS["SC"] for op, w in OPERATION_WRAPS.items()}

# Typical hook midpoints by CYC yarn weight (mm), used only when no hook is given.
CYC_TYPICAL_HOOK_MM = {0: 1.75, 1: 2.75, 2: 4.0, 3: 5.0, 4: 6.0, 5: 8.0, 6: 11.0, 7: 16.0}


def _positive(name: str, value: float):
    if value is None or value <= 0:
        raise ValueError(f"{name} must be > 0")


def loop_per_wrap_mm(hook_mm: float, yarn_diameter_mm: float) -> float:
    """Yarn consumed by one yarn pass: one loop around hook + yarn, less tension."""
    _positive("hook_mm", hook_mm)
    _positive("yarn_diameter_mm", yarn_diameter_mm)
    return TENSION_FACTOR * pi * (hook_mm + yarn_diameter_mm)


def estimate_hook_mm(yarn_diameter_mm: float, cyc_weight: int | None = None) -> float:
    """Fallback hook size when the user did not enter one."""
    if cyc_weight is not None and int(cyc_weight) in CYC_TYPICAL_HOOK_MM:
        return CYC_TYPICAL_HOOK_MM[int(cyc_weight)]
    _positive("yarn_diameter_mm", yarn_diameter_mm)
    return 2.0 * yarn_diameter_mm


@dataclass(frozen=True)
class BaselineOperationLength:
    operation_id: str
    length_mm: float
    lower_mm: float
    upper_mm: float
    measured_anchor: bool
    high_uncertainty: bool


def operation_length_mm(operation_id: str, hook_mm: float, yarn_diameter_mm: float) -> BaselineOperationLength:
    if operation_id not in OPERATION_WRAPS:
        raise KeyError(f"no geometry baseline defined for operation {operation_id}")
    length_mm = OPERATION_WRAPS[operation_id] * loop_per_wrap_mm(hook_mm, yarn_diameter_mm)
    high = operation_id in HIGH_UNCERTAINTY_OPERATIONS
    measured = operation_id in MEASURED_ANCHOR_OPERATIONS
    half = MEASURED_HALF_WIDTH if measured else TEXTURE_HALF_WIDTH if high else EXTRAPOLATED_HALF_WIDTH
    return BaselineOperationLength(operation_id, length_mm, length_mm * (1 - half), length_mm * (1 + half), measured, high)


def program_length_mm(operation_counts: dict, hook_mm: float, yarn_diameter_mm: float):
    """Sum baseline length across a canonical operation-count program.

    Returns (core_length_mm, lower_mm, upper_mm, warnings, unsupported_ops).
    Unknown operation ids are skipped and reported so callers can decide
    whether to fail or proceed with a partial, flagged estimate.
    """
    total = lower = upper = 0.0
    warnings, unsupported = [], []
    used_high = used_extrapolated = False
    for op, n in operation_counts.items():
        n = int(n)
        if n <= 0:
            continue
        if op not in OPERATION_WRAPS:
            unsupported.append(op)
            continue
        one = operation_length_mm(op, hook_mm, yarn_diameter_mm)
        total += one.length_mm * n
        lower += one.lower_mm * n
        upper += one.upper_mm * n
        used_high |= one.high_uncertainty
        used_extrapolated |= not (one.measured_anchor or one.high_uncertainty)
    warnings.append(
        "uncalibrated geometry baseline: yarn per stitch = yarn passes x loop around hook+yarn "
        f"(tension factor {TENSION_FACTOR}); checked against published SC/HDC/DC swatch measurements "
        "(Interweave yarn-usage experiment) and the (17 +/- 8)% tension effect reported by "
        "Storck et al. 2022 (DOI 10.1177/15280837221139250). Your yarn and tension will differ; "
        "a measured swatch replaces this estimate.")
    if used_extrapolated:
        warnings.append("this program includes stitch types beyond SC/HDC/DC; their length follows the yarn-pass count and was not checked against a measurement")
    if used_high:
        warnings.append("this program includes texture stitches (puff/popcorn) whose construction varies; uncertainty band widened")
    if unsupported:
        warnings.append("no geometry baseline for operations: " + ", ".join(sorted(set(unsupported))) + " (excluded from this estimate)")
    return total, lower, upper, tuple(warnings), tuple(unsupported)
