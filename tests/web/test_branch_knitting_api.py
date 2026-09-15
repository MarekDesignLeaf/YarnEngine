from fastapi.testclient import TestClient
from src.web.app import app
def test_branch_api():
 p={"initial_stitches":8,"steps":[
 {"type":"split","group":"G0","targets":[{"id":"A","stitches":4},{"id":"B","stitches":4}]},
 {"type":"row","group":"A","instruction":"K4"},
 {"type":"row","group":"B","instruction":"P4"},
 {"type":"join","groups":["A","B"],"target":"BODY"}]}
 r=TestClient(app).post("/api/branch-knitting/execute",json=p)
 assert r.status_code==200 and r.json()["valid"] and r.json()["live_stitches"]==8
