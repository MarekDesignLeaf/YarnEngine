from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_shaping_endpoint():
 p={"pattern_id":"API_SHAPE","name":"API Shape","initial_stitches":4,
 "rows":[{"row":1,"side":"RS","instruction":"KFB, K3"},
         {"row":2,"side":"WS","instruction":"K2TOG, K3"}]}
 r=c.post("/api/shaping/translate",json=p)
 assert r.status_code==200 and r.json()["valid"] and r.json()["final_stitches"]==4
