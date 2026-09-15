from fastapi.testclient import TestClient
from src.web.app import app
def test_uncertainty_endpoint():
 r=TestClient(app).post("/api/validation/uncertainty",json={"estimate_m":100,"validation_errors":[1,-2,3,-4],"confidence":.95})
 assert r.status_code==200
 d=r.json();assert d["validation"]["n"]==4 and not d["interval"]["calibrated"]
