"""Estimate a working yarn diameter when the record has no measured value.

Preference order (best evidence first):
1. nominal_diameter_mm stored on the yarn record;
2. wraps-per-inch (WPI): diameter = 25.4 / WPI;
3. Craft Yarn Council weight category, via a typical WPI for that category;
4. linear density (tex), treating the yarn as a lofty cylinder.

Every non-measured path returns a warning string so callers can surface it.
"""
from math import pi, sqrt

# Typical wraps-per-inch midpoints by CYC weight category (0 lace .. 7 jumbo).
CYC_TYPICAL_WPI = {0: 35.0, 1: 20.0, 2: 16.0, 3: 13.0, 4: 10.0, 5: 7.5, 6: 5.5, 7: 3.0}

# Effective bulk density of a lofty hand-craft yarn (fibre density x packing).
LOFTY_BULK_DENSITY_G_CM3 = 0.2


def diameter_from_wpi(wpi: float) -> float:
    if wpi <= 0:
        raise ValueError("wpi must be > 0")
    return 25.4 / wpi


def diameter_from_tex(tex: float, bulk_density_g_cm3: float = LOFTY_BULK_DENSITY_G_CM3) -> float:
    if tex <= 0 or bulk_density_g_cm3 <= 0:
        raise ValueError("tex and density must be > 0")
    area_mm2 = tex / (1000.0 * bulk_density_g_cm3)
    return 2.0 * sqrt(area_mm2 / pi)


def estimate_yarn_diameter_mm(yarn: dict | None, explicit_mm: float | None = None):
    """Return (diameter_mm, source, warnings)."""
    if explicit_mm:
        return float(explicit_mm), "explicit", ()
    if not yarn:
        return None, None, ("no yarn selected and no yarn diameter supplied",)
    if yarn.get("nominal_diameter_mm"):
        return float(yarn["nominal_diameter_mm"]), "yarn_record", ()
    if yarn.get("wpi"):
        return diameter_from_wpi(float(yarn["wpi"])), "wpi", ("yarn diameter derived from wraps-per-inch, not measured directly",)
    cyc = yarn.get("cyc_weight")
    if cyc is not None and int(cyc) in CYC_TYPICAL_WPI:
        return diameter_from_wpi(CYC_TYPICAL_WPI[int(cyc)]), "cyc_weight", (
            f"yarn diameter assumed from typical wraps-per-inch for CYC weight {int(cyc)}; measure WPI for a better estimate",)
    tex = yarn.get("tex")
    if tex:
        return diameter_from_tex(float(tex)), "tex", (
            "yarn diameter estimated from linear density assuming a lofty yarn; measure WPI or diameter for a better estimate",)
    return None, None, ("yarn record has no diameter, WPI, weight category or tex",)
