import json
from pathlib import Path
from src.calibration_capture.record import RealSwatchRecord,MeasurementEvidence
from src.calibration_capture.replicates import summarize_replicates,flag_unstable_replicates
ROOT=Path(__file__).resolve().parents[2]
def load():
    raw=json.loads((ROOT/"data/calibration/synthetic_m31_workflow_records.json").read_text())["records"]
    return [RealSwatchRecord(**{**x,"evidence":MeasurementEvidence(**x["evidence"])}) for x in raw]
def test_replicate_summary():
    r=summarize_replicates(load())
    assert len(r)==3
    assert all(x.n==3 for x in r)
def test_flags_none_at_loose_threshold():
    assert flag_unstable_replicates(load(),cv_threshold_percent=10,min_replicates=3)==()
