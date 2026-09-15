"""Published loop-element geometry adapted as a Tier-B theoretical model.

Source:
E. Arbataitis et al., Materials 2021, 14, 3059.
https://doi.org/10.3390/ma14113059

The cited research applies Čiukas geometric modelling to weft-knitted fabrics.
It was experimentally studied on machine-knitted structures. This module therefore
does NOT claim direct hand-knitting accuracy. Results must be calibrated/validated
before production use.

All lengths are millimetres.
"""
from math import pi

def _positive(name: str, value: float):
    if value <= 0:
        raise ValueError(f"{name} must be > 0")

def single_bar_needle_loop_mm(A: float, B: float, d: float) -> float:
    """Formula (5): l_s = 0.5*pi*(0.5*A + d) + 2*B."""
    for n,v in (("A",A),("B",B),("d",d)): _positive(n,v)
    return 0.5 * pi * (0.5 * A + d) + 2.0 * B

def horizontal_float_mm(A: float, d: float, i: int = 2) -> float:
    """Formula (7): l_h = 0.5*pi*(0.25*i*A + d); i must be positive even."""
    _positive("A",A); _positive("d",d)
    if i <= 0 or i % 2 != 0:
        raise ValueError("horizontal-float index i must be a positive even integer")
    return 0.5 * pi * (0.25 * i * A + d)

def plain_loop_path_mm(A: float, B: float, d: float) -> float:
    """One single-bar needle loop plus its adjacent shortest horizontal float.

    This is an engineering composition of published element formulae, suitable
    only as a Tier-B baseline until calibrated for the target knitting process.
    """
    return single_bar_needle_loop_mm(A,B,d) + horizontal_float_mm(A,d,2)
