from fastapi.testclient import TestClient
from src.web.app import app
def test_amigurumi_api():
 r=TestClient(app).post("/api/crochet/amigurumi/analyse",json={"initial_stitches":6,"rounds":[{"operations":{"SC_INC":6}},{"operations":{"SC":12}}]})
 assert r.status_code==200 and r.json()["valid"] and r.json()["final_stitches"]==12
