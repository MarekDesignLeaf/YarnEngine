from fastapi.testclient import TestClient
from src.web.app import app
def test_scaling_gate_api():
 r=TestClient(app).post("/api/library-scaling/gate",json={"items":[],"target":100})
 assert r.status_code==200 and not r.json()["ready"] and r.json()["portfolio"]["total"]==0
