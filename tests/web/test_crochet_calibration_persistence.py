from fastapi.testclient import TestClient
import src.web.app as wa
from src.crochet_calibration.store import CrochetCalibrationStore
def test_persistent_record_api(tmp_path,monkeypatch):
 s=CrochetCalibrationStore(tmp_path/"c.sqlite");monkeypatch.setattr(wa,"crochet_cal_store",s)
 c=TestClient(wa.app)
 p={"record_id":"r1","replicate_group_id":"g","crocheter_id":"c","yarn_id":"y","hook_mm":3,
 "gauge_stitches":20,"gauge_rows":20,"gauge_width_mm":100,"gauge_height_mm":100,
 "operation_counts":{"SC":400},"yarn_length_m":10,"yarn_diameter_mm":2,"construction":"spiral"}
 assert c.post("/api/crochet/calibration/records",json=p).status_code==200
 assert len(c.get("/api/crochet/calibration/records").json())==1
 assert c.get("/api/crochet/calibration/status").json()["ready"] is False
 s.close()
