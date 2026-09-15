from dataclasses import dataclass
from math import sqrt
from .features import build_feature_spec, sample_feature_vector, feature_names

def _solve(a,b):
    n=len(a)
    aug=[list(map(float,a[i]))+[float(b[i])] for i in range(n)]
    for col in range(n):
        pivot=max(range(col,n),key=lambda r:abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            raise ValueError("singular calibration matrix")
        aug[col],aug[pivot]=aug[pivot],aug[col]
        div=aug[col][col]
        aug[col]=[x/div for x in aug[col]]
        for r in range(n):
            if r==col: continue
            f=aug[r][col]
            if f:
                aug[r]=[aug[r][c]-f*aug[col][c] for c in range(n+1)]
    return [aug[i][-1] for i in range(n)]

def _mat_t_mat(X):
    p=len(X[0])
    return [[sum(row[i]*row[j] for row in X) for j in range(p)] for i in range(p)]

def _mat_t_vec(X,y):
    p=len(X[0])
    return [sum(X[r][i]*y[r] for r in range(len(X))) for i in range(p)]

@dataclass(frozen=True)
class LinearCalibrationModel:
    feature_names: tuple[str,...]
    coefficients: tuple[float,...]
    operation_ids: tuple[str,...]
    rmse_m: float
    mae_m: float
    mean_error_m: float
    residual_std_m: float
    n_samples: int
    ridge_lambda: float
    domains: dict

    def predict_vector(self,x):
        return sum(c*v for c,v in zip(self.coefficients,x))

def fit_linear_model(samples, ridge_lambda: float = 1e-6):
    samples=list(samples)
    if len(samples) < 2:
        raise ValueError("at least 2 calibration samples required")
    spec=build_feature_spec(samples)
    X=[sample_feature_vector(s,spec) for s in samples]
    y=[s.yarn_length_m for s in samples]
    xtx=_mat_t_mat(X); xty=_mat_t_vec(X,y)
    # ridge regularization, excluding intercept
    for i in range(len(xtx)):
        if not (spec.include_intercept and i==0):
            xtx[i][i]+=ridge_lambda
    beta=_solve(xtx,xty)
    pred=[sum(c*v for c,v in zip(beta,row)) for row in X]
    residuals=[yy-pp for yy,pp in zip(y,pred)]
    n=len(residuals)
    rmse=sqrt(sum(r*r for r in residuals)/n)
    mae=sum(abs(r) for r in residuals)/n
    bias=sum(residuals)/n
    rsd=sqrt(sum((r-bias)**2 for r in residuals)/(n-1)) if n>1 else 0.0
    domains={
      "wale_spacing_mm":[min(s.wale_spacing_mm for s in samples),max(s.wale_spacing_mm for s in samples)],
      "course_spacing_mm":[min(s.course_spacing_mm for s in samples),max(s.course_spacing_mm for s in samples)],
      "yarn_diameter_mm":[
          min((s.yarn_diameter_mm for s in samples if s.yarn_diameter_mm is not None),default=None),
          max((s.yarn_diameter_mm for s in samples if s.yarn_diameter_mm is not None),default=None)
      ],
      "operation_ids":list(spec.operation_ids)
    }
    return LinearCalibrationModel(
        tuple(feature_names(spec)),tuple(beta),spec.operation_ids,
        rmse,mae,bias,rsd,n,ridge_lambda,domains
    ), spec
