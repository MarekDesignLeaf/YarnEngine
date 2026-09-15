from dataclasses import dataclass

@dataclass(frozen=True)
class PredictionRange:
    estimate_m: float
    lower_m: float
    upper_m: float
    relative_half_width: float
    basis: str

def percentage_range(estimate_m: float, relative_half_width: float, basis: str) -> PredictionRange:
    if estimate_m < 0:
        raise ValueError("estimate_m must be >= 0")
    if not (0 <= relative_half_width < 1):
        raise ValueError("relative_half_width must be in [0,1)")
    return PredictionRange(
        estimate_m=estimate_m,
        lower_m=estimate_m * (1-relative_half_width),
        upper_m=estimate_m * (1+relative_half_width),
        relative_half_width=relative_half_width,
        basis=basis
    )
