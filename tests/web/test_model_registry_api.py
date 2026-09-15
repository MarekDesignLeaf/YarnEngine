from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_registry_list_and_quality():
 assert c.get("/api/models").status_code==200
 r=c.get("/api/calibration-lab/quality");assert r.status_code==200 and "protocol" in r.json()
