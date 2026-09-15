from fastapi.testclient import TestClient
from src.web.app import app
def test_empty_calibration_not_ready():
 r=TestClient(app).post("/api/crochet/calibration/readiness",json={"records":[]})
 assert r.status_code==200 and not r.json()["ready"]
