import json
from pathlib import Path
from src.calibration.dataset import CalibrationSample
from src.calibration.linear import fit_linear_model
from src.calibration.predict import predict_sample
ROOT=Path(__file__).resolve().parents[2]

def load():
    raw=json.loads((ROOT/"data/calibration/synthetic_m3_test_dataset.json").read_text())
    return [CalibrationSample(**x) for x in raw["samples"]]

def test_fit_has_metrics():
    m,s=fit_linear_model(load(),1e-4)
    assert m.n_samples==10
    assert m.rmse_m>=0 and m.mae_m>=0
    assert "op:K/1000" in m.feature_names

def test_prediction_in_domain():
    samples=load(); m,s=fit_linear_model(samples,1e-4)
    p=predict_sample(samples[0],m,s)
    assert p.estimate_m>0
    assert p.in_domain

def test_ood_gauge_warns():
    samples=load(); m,s=fit_linear_model(samples,1e-4)
    x=samples[0]
    bad=CalibrationSample("OOD","X",x.operation_counts,1.0,8.0,x.course_spacing_mm,x.yarn_diameter_mm,x.tex)
    p=predict_sample(bad,m,s)
    assert not p.in_domain
    assert any("outside calibrated range" in w for w in p.warnings)
