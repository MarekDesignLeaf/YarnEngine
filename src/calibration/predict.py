from dataclasses import dataclass
from math import sqrt
from .dataset import CalibrationSample
from .features import FeatureSpec, sample_feature_vector
from .uncertainty import empirical_absolute_error_interval

@dataclass(frozen=True)
class Prediction:
    estimate_m: float
    lower_95_m: float
    upper_95_m: float
    in_domain: bool
    warnings: tuple[str,...]

def domain_check(sample: CalibrationSample, model) -> tuple[bool,list[str]]:
    warnings=[]
    known=set(model.domains.get("operation_ids",[]))
    used={op for op,n in sample.operation_counts.items() if n>0}
    unknown=sorted(used-known)
    if unknown:
        warnings.append("unseen operations: "+", ".join(unknown))
    for field in ("wale_spacing_mm","course_spacing_mm"):
        lo,hi=model.domains[field]
        val=getattr(sample,field)
        if val < lo or val > hi:
            warnings.append(f"{field}={val:.4g} outside calibrated range [{lo:.4g}, {hi:.4g}]")
    dr=model.domains.get("yarn_diameter_mm",[None,None])
    if sample.yarn_diameter_mm is not None and dr[0] is not None:
        if sample.yarn_diameter_mm < dr[0] or sample.yarn_diameter_mm > dr[1]:
            warnings.append(f"yarn_diameter_mm={sample.yarn_diameter_mm:.4g} outside calibrated range [{dr[0]:.4g}, {dr[1]:.4g}]")
    return len(warnings)==0,warnings

def predict_sample(sample: CalibrationSample, model, spec: FeatureSpec, validation_errors=None) -> Prediction:
    x=sample_feature_vector(sample,spec)
    estimate=model.predict_vector(x)
    in_domain,warnings=domain_check(sample,model)
    if validation_errors:
        interval=empirical_absolute_error_interval(estimate,validation_errors)
        half=interval.half_width_m
        if interval.warning:warnings.append(interval.warning)
        warnings.append("uncertainty uses held-out empirical absolute-error coverage, not a parametric regression prediction interval")
    else:
        # Research fallback only. Training residual spread is not validation evidence.
        half=1.96*model.residual_std_m
        warnings.append("uncertainty fallback uses training residual spread; held-out validation errors are unavailable")
    if not in_domain:
        half=max(half,abs(estimate)*0.25)
        warnings.append("uncertainty widened because prediction is outside the calibration domain")
    return Prediction(max(0.0,estimate),max(0.0,estimate-half),max(0.0,estimate+half),in_domain,tuple(warnings))
