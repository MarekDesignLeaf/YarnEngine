from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_lab_status():
 r=c.get("/api/calibration-lab/status");assert r.status_code==200
 d=r.json();assert "ready" in d and "coverage" in d and "excluded" in d
