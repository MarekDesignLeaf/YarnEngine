import json
from dataclasses import asdict
from pathlib import Path
from .linear import LinearCalibrationModel
from .features import FeatureSpec

def save_model(path,model,spec):
    payload={"model":asdict(model),"feature_spec":asdict(spec)}
    Path(path).write_text(json.dumps(payload,indent=2),encoding="utf-8")

def load_model(path):
    p=json.loads(Path(path).read_text(encoding="utf-8"))
    m=p["model"]; s=p["feature_spec"]
    model=LinearCalibrationModel(
      tuple(m["feature_names"]),tuple(m["coefficients"]),tuple(m["operation_ids"]),
      m["rmse_m"],m["mae_m"],m["mean_error_m"],m["residual_std_m"],
      m["n_samples"],m["ridge_lambda"],m["domains"]
    )
    spec=FeatureSpec(tuple(s["operation_ids"]),s["include_intercept"],s["include_wale"],s["include_course"],s["include_diameter"])
    return model,spec
