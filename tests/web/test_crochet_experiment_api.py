from fastapi.testclient import TestClient
import src.web.app as wa
from src.crochet_calibration.store import CrochetCalibrationStore
def test_experiment_plan_api(tmp_path,monkeypatch):
 s=CrochetCalibrationStore(tmp_path/"c.sqlite");monkeypatch.setattr(wa,"crochet_cal_store",s)
 r=TestClient(wa.app).post("/api/crochet/calibration/experiment-plan",json={"required_ops":["SC"],"min_records_per_op":1,"min_replicates":1})
 assert r.status_code==200 and r.json()["count"]==1
 s.close()
