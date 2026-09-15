from dataclasses import dataclass

@dataclass(frozen=True)
class CompatibilityResult:
    compatible:bool
    score:float
    reasons:tuple[str,...]
    warnings:tuple[str,...]

def assess_yarn_for_gauge(yarn,stitches_per_10cm,needle_mm=None):
    """Screening only, never substitutes for a swatch."""
    reasons=[]; warnings=[]; score=100.0
    # CYC guideline stockinette gauge bands, used only as a broad screening range.
    bands={0:(33,40),1:(27,32),2:(23,26),3:(21,24),4:(16,20),5:(12,15),6:(7,11),7:(0,6)}
    if yarn.cyc_weight is not None:
        lo,hi=bands[yarn.cyc_weight]
        if not (lo<=stitches_per_10cm<=hi):
            score-=35
            warnings.append("requested gauge is outside the broad CYC stockinette guideline for this yarn weight")
        else:
            reasons.append("requested gauge falls inside the broad CYC stockinette guideline")
    if needle_mm is not None and yarn.recommended_needle_min_mm is not None and yarn.recommended_needle_max_mm is not None:
        if yarn.recommended_needle_min_mm<=needle_mm<=yarn.recommended_needle_max_mm:
            reasons.append("needle size is inside yarn's declared recommendation")
        else:
            score-=15; warnings.append("needle size is outside yarn's declared recommendation")
    warnings.append("compatibility is provisional until gauge is verified with a swatch")
    return CompatibilityResult(score>=50,max(0.0,score),tuple(reasons),tuple(warnings))
