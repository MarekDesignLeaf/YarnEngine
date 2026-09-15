from dataclasses import asdict
from src.calibration.dataset import CalibrationSample
from src.calibration.linear import fit_linear_model
from src.calibration.validation import leave_one_out

def samples_from_records(records):
    return [CalibrationSample(
      calibration_id=f"swatch:{r.swatch_id}",pattern_id=r.pattern_id,operation_counts=r.operation_counts,
      yarn_length_m=float(r.yarn_length_m),wale_spacing_mm=r.wale_spacing_mm,course_spacing_mm=r.course_spacing_mm,
      yarn_diameter_mm=r.yarn_diameter_mm,tex=r.tex
    ) for r in records if r.yarn_length_m is not None]

def fit_report(records,ridge_lambda=1e-6):
    samples=samples_from_records(records)
    model,spec=fit_linear_model(samples,ridge_lambda)
    cv=None;cv_error=None
    if len(samples)>=4:
        try:
            x=leave_one_out(samples,ridge_lambda);cv=asdict(x)
        except ValueError as e:cv_error=str(e)
    return {
      "model":{"feature_names":list(model.feature_names),"coefficients":list(model.coefficients),
       "operation_ids":list(model.operation_ids),"rmse_m":model.rmse_m,"mae_m":model.mae_m,
       "mean_error_m":model.mean_error_m,"residual_std_m":model.residual_std_m,"n_samples":model.n_samples,
       "ridge_lambda":model.ridge_lambda,"domains":model.domains},
      "feature_spec":{"operation_ids":list(spec.operation_ids),"include_intercept":spec.include_intercept,
       "include_wale":spec.include_wale,"include_course":spec.include_course,"include_diameter":spec.include_diameter},
      "leave_one_out":cv,"validation_error":cv_error,
      "warning":"Research calibration model. Training fit is not evidence of generalization; validation and independent real data are required."
    }
