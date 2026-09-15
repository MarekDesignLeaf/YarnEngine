import pytest
from src.crochet_calibration.record import CrochetCalibrationRecord
from src.crochet_calibration.protocol import readiness
def rec(i,op="SC",group="g"):
 return CrochetCalibrationRecord(str(i),group,"c","y",3.0,20,20,100,100,{op:400},10.0,
  yarn_diameter_mm=2.0,construction="spiral")
def test_record_rejects_knit_operation():
 with pytest.raises(ValueError):CrochetCalibrationRecord("1","g","c","y",3,20,20,100,100,{"K":400},10)
def test_readiness_exposes_missing_ops():
 r=readiness([rec(1),rec(2),rec(3)],required_ops=("SC","SC_INC"))
 assert not r["ready"] and any("SC_INC" in x for x in r["reasons"])
def test_configurable_minimal_ready_fixture():
 r=readiness([rec(1),rec(2),rec(3)],required_ops=("SC",),min_records_per_op=3,min_replicates=3)
 assert r["ready"]
