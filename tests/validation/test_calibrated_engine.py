import json
from pathlib import Path
from src.calibration.dataset import CalibrationSample
from src.calibration.linear import fit_linear_model
from src.consumption.calibrated_engine import calculate_calibrated
ROOT=Path(__file__).resolve().parents[2]
def test_end_to_end_calibrated():
    raw=json.loads((ROOT/"data/calibration/synthetic_m3_test_dataset.json").read_text())
    samples=[CalibrationSample(**x) for x in raw["samples"]]
    m,s=fit_linear_model(samples,1e-4)
    r=calculate_calibrated(operation_counts={"K":800,"P":800},wale_spacing_mm=5.0,course_spacing_mm=4.0,
                           yarn_diameter_mm=1.0,model=m,spec=s,allowance_percent=8,tex=250,package_length_m=200)
    assert r.core_length_m>0
    assert r.recommended_length_m>r.core_length_m
    assert r.mass_g is not None
    assert r.packages is not None
