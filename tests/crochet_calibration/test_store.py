from src.crochet_calibration.store import CrochetCalibrationStore
from src.crochet_calibration.record import CrochetCalibrationRecord
def rec(i):
 return CrochetCalibrationRecord(str(i),"g","c","y",3,20,20,100,100,{"SC":400},10,yarn_diameter_mm=2,construction="spiral")
def test_store_roundtrip(tmp_path):
 s=CrochetCalibrationStore(tmp_path/"c.sqlite");s.add(rec(1))
 assert s.get("1")["operation_counts"]["SC"]==400 and len(s.records())==1
 assert s.delete("1") and s.get("1") is None;s.close()
