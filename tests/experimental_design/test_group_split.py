import json
from pathlib import Path
from src.calibration_capture.record import RealSwatchRecord,MeasurementEvidence
from src.experimental_design.group_split import leave_one_group_out,grouped_holdout
ROOT=Path(__file__).resolve().parents[2]
def load():
    raw=json.loads((ROOT/"data/calibration/synthetic_m31_workflow_records.json").read_text())["records"]
    return [RealSwatchRecord(**{**x,"evidence":MeasurementEvidence(**x["evidence"])}) for x in raw]
def test_logo_knitter():
    folds=leave_one_group_out(load(),"knitter_id")
    assert len(folds)==2
    for f in folds:
        assert set(f["train_indices"]).isdisjoint(f["test_indices"])
def test_group_holdout():
    s=grouped_holdout(load(),"yarn_id",0.5)
    assert s["train_indices"] and s["test_indices"]
