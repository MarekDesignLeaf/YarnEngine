from src.calibration.dataset import CalibrationSample
from src.calibration.linear import fit_linear_model
from src.calibration.validation import leave_one_out
from dataclasses import asdict

def samples(records):
    return [CalibrationSample(r.record_id,"crochet:"+r.construction,dict(r.operation_counts),r.yarn_length_m,
      r.wale_spacing_mm,r.course_spacing_mm,r.yarn_diameter_mm,r.tex) for r in records]

def fit_crochet_model(records,ridge_lambda=1e-6):
    ss=samples(records);model,spec=fit_linear_model(ss,ridge_lambda)
    cv=None;err=None
    if len(ss)>=4:
        try:cv=asdict(leave_one_out(ss,ridge_lambda))
        except ValueError as e:err=str(e)
    return {"model":{"feature_names":list(model.feature_names),"coefficients":list(model.coefficients),
      "operation_ids":list(model.operation_ids),"rmse_m":model.rmse_m,"mae_m":model.mae_m,
      "mean_error_m":model.mean_error_m,"residual_std_m":model.residual_std_m,"n_samples":model.n_samples,
      "ridge_lambda":model.ridge_lambda,"domains":model.domains},
      "feature_spec":{"operation_ids":list(spec.operation_ids),"include_intercept":spec.include_intercept,
      "include_wale":spec.include_wale,"include_course":spec.include_course,"include_diameter":spec.include_diameter},
      "leave_one_out":cv,"validation_error":err,
      "model_scope":"crochet","warning":"No production accuracy claim until real measured crochet validation passes governance gates."}
