from src.calibration.linear import LinearCalibrationModel
from src.calibration.features import FeatureSpec
from src.calibration.dataset import CalibrationSample
from src.calibration.predict import predict_sample
from src.consumption.engine import _finalize
from src.gauge_engine.gauge import project_grid

MODEL_SCHEMA_VERSION="m8-model-1"
FEATURE_SPEC_VERSION="m8-feature-spec-1"

def hydrate_model(record):
 m=record["model"]
 model=LinearCalibrationModel(
  tuple(m["feature_names"]),tuple(m["coefficients"]),tuple(m["operation_ids"]),
  m["rmse_m"],m["mae_m"],m["mean_error_m"],m["residual_std_m"],m["n_samples"],m["ridge_lambda"],m["domains"])
 ops=tuple(m["operation_ids"])
 spec=FeatureSpec(ops,True,True,True)
 return model,spec

def calculate_with_production_model(*,record,operation_counts,gauge,width_mm,height_mm,
 yarn_diameter_mm,allowance_percent,tex=None,package_length_m=None,domain_policy="strict"):
 model,spec=hydrate_model(record)
 sample=CalibrationSample(
  calibration_id="runtime",pattern_id="runtime",operation_counts=operation_counts,yarn_length_m=1e-12,
  wale_spacing_mm=gauge.wale_spacing_mm,course_spacing_mm=gauge.course_spacing_mm,
  yarn_diameter_mm=yarn_diameter_mm,tex=tex)
 validation=record.get("validation") or {}
 def _find_errors(x):
  if isinstance(x,dict):
   if isinstance(x.get("errors"),list):return x["errors"]
   for v in x.values():
    found=_find_errors(v)
    if found:return found
  return None
 validation_errors=_find_errors(validation)
 pred=predict_sample(sample,model,spec,validation_errors=validation_errors)
 if domain_policy not in {"strict","warn","research"}:
  raise ValueError("invalid domain policy")
 if not pred.in_domain and domain_policy=="strict":
  raise ValueError("production prediction is outside the calibrated domain")
 grid=project_grid(width_mm,height_mm,gauge)
 calc=_finalize("B",pred.estimate_m,grid,allowance_percent,tex,package_length_m,
  status="production_calibration_model" if pred.in_domain else f"production_model_out_of_domain_{domain_policy}",
  warnings=pred.warnings)
 return calc,pred
