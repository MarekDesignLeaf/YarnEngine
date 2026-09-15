import json
from pathlib import Path
from src.calibration_capture.record import RealSwatchRecord,MeasurementEvidence
from src.experimental_design.coverage import analyse_coverage
from src.experimental_design.prioritize import SwatchCandidate,rank_candidates
ROOT=Path(__file__).resolve().parents[2]
def load():
    raw=json.loads((ROOT/"data/calibration/synthetic_m31_workflow_records.json").read_text())["records"]
    return [RealSwatchRecord(**{**x,"evidence":MeasurementEvidence(**x["evidence"])}) for x in raw]
def test_coverage():
    c=analyse_coverage(load(),min_records_per_operation=5)
    assert c.distinct_patterns==3
    assert "C2_2R" in c.undercovered_operations
def test_unseen_operation_ranks_high():
    c=analyse_coverage(load())
    cs=[
      SwatchCandidate("A","STOCKINETTE","Y1","K1",{"K":1000},5,4,1),
      SwatchCandidate("B","LACE_NEW","Y3","K3",{"YO":200,"K2TOG":200,"K":600},5,4,1)
    ]
    r=rank_candidates(cs,c)
    assert r[0].candidate_id=="B"
    assert any("unseen operations" in x for x in r[0].reasons)
