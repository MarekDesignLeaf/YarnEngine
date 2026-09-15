from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_groups_api():
 p={"initial_stitches":12,"events":[
 {"step":1,"action":"split","source_ids":["G0"],"target_ids":["L","R"],"counts":[6,6]},
 {"step":2,"action":"hold","source_ids":["R"]},
 {"step":3,"action":"resume","source_ids":["R"]},
 {"step":4,"action":"join","source_ids":["L","R"],"target_ids":["BODY"]}]}
 r=c.post("/api/stitch-groups/analyse",json=p)
 d=r.json()
 assert r.status_code==200 and d["valid"] and d["groups"]["BODY"]["stitches"]==12
