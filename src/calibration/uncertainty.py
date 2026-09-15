from dataclasses import dataclass
from math import sqrt

@dataclass(frozen=True)
class EmpiricalInterval:
    lower_m: float
    upper_m: float
    half_width_m: float
    method: str
    confidence_nominal: float
    n_validation_errors: int
    calibrated: bool
    warning: str | None = None

def _quantile(values,q):
    xs=sorted(float(x) for x in values)
    if not xs: raise ValueError("quantile requires data")
    if len(xs)==1:return xs[0]
    pos=(len(xs)-1)*q;lo=int(pos);hi=min(lo+1,len(xs)-1);w=pos-lo
    return xs[lo]*(1-w)+xs[hi]*w

def empirical_absolute_error_interval(estimate_m, validation_errors, confidence=0.95):
    """Symmetric empirical interval from held-out absolute errors.
    It is intentionally not called a formal regression prediction interval."""
    if not 0 < confidence < 1: raise ValueError("confidence must be between 0 and 1")
    errs=[abs(float(e)) for e in validation_errors]
    if not errs:
        return EmpiricalInterval(max(0.0,estimate_m),estimate_m,0.0,"none",confidence,0,False,
          "No held-out validation errors are available; no empirical uncertainty interval can be claimed.")
    half=_quantile(errs,confidence)
    calibrated=len(errs)>=20
    warning=None if calibrated else (
      "Empirical interval is based on fewer than 20 held-out errors; coverage is descriptive and not production-validated.")
    return EmpiricalInterval(max(0.0,estimate_m-half),max(0.0,estimate_m+half),half,
      "held_out_absolute_error_quantile",confidence,len(errs),calibrated,warning)

def validation_summary(errors):
    errors=[float(x) for x in errors]
    if not errors:return {"n":0,"mae_m":None,"rmse_m":None,"bias_m":None,"absolute_error_p95_m":None}
    n=len(errors);mae=sum(abs(x) for x in errors)/n;rmse=sqrt(sum(x*x for x in errors)/n);bias=sum(errors)/n
    return {"n":n,"mae_m":mae,"rmse_m":rmse,"bias_m":bias,
            "absolute_error_p95_m":_quantile([abs(x) for x in errors],.95)}
