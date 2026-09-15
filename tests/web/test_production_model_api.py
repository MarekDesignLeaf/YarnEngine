from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_current_production_endpoint():
 r=c.get("/api/models/production/current");assert r.status_code==200 and "active" in r.json()
def test_calibrated_rejected_without_production():
 # Default test DB should have no approved production model.
 p={"pattern_id":"STOCKINETTE","pattern_version":"1.0.0","width_cm":10,"height_cm":10,
 "gauge_stitches_per_10cm":20,"gauge_rows_per_10cm":28,"calculation_mode":"calibrated"}
 r=c.post("/api/calculate",json=p);assert r.status_code==422
