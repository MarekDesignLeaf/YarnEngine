from src.crochet_calibration.record import CrochetCalibrationRecord
from src.crochet_calibration.audit import dataset_snapshot,calibration_audit
def r(i,length=10):
 return CrochetCalibrationRecord(str(i),"g","c","y",3,20,20,100,100,{"SC":400},length,yarn_diameter_mm=2,construction="spiral")
def test_snapshot_is_order_independent():
 assert dataset_snapshot([r(2),r(1)])["dataset_sha256"]==dataset_snapshot([r(1),r(2)])["dataset_sha256"]
def test_changed_measurement_changes_hash():
 assert dataset_snapshot([r(1,10)])["dataset_sha256"]!=dataset_snapshot([r(1,11)])["dataset_sha256"]
def test_audit_has_integrity_hash():
 a=calibration_audit([r(1)],{"ready":False},{"overall":"insufficient"},{"valid":True,"issues":[]})
 assert len(a["audit_sha256"])==64 and len(a["dataset"]["dataset_sha256"])==64
