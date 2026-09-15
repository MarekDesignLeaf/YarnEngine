import json,tempfile
from pathlib import Path
from src.calibration.dataset import CalibrationSample
from src.calibration.linear import fit_linear_model
from src.calibration.serialization import save_model,load_model
ROOT=Path(__file__).resolve().parents[2]
def test_roundtrip(tmp_path):
    raw=json.loads((ROOT/"data/calibration/synthetic_m3_test_dataset.json").read_text())
    samples=[CalibrationSample(**x) for x in raw["samples"]]
    m,s=fit_linear_model(samples,1e-4)
    p=tmp_path/"model.json"; save_model(p,m,s); m2,s2=load_model(p)
    assert m.feature_names==m2.feature_names
    assert len(m.coefficients)==len(m2.coefficients)
