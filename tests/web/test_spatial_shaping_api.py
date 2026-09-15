from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_spatial_api():
 p={"pattern_id":"API_SPATIAL","name":"API Spatial","initial_stitches":4,
 "gauge_preview":{"stitch_width_mm":4,"row_height_mm":3},
 "rows":[{"row":1,"side":"RS","instruction":"KFB, K2, KFB"},
         {"row":2,"side":"WS","instruction":"K6"},
         {"row":3,"side":"RS","instruction":"K2TOG, K2, K2TOG"}]}
 r=c.post("/api/spatial-shaping/analyse",json=p)
 d=r.json()
 assert r.status_code==200 and d["valid"] and len(d["topology"]["rows"][0]["shaping_events"])==2
