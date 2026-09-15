from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_acquisition_endpoint():
 p={"pattern_id":"ACQ_API","name":"Acq API","repeat":{"width_stitches":2,"height_rows":1},
 "rows":[{"row":1,"side":"RS","instruction":"K2"}],
 "metadata":{"family_id":"PLAIN","difficulty":"basic","techniques":["knitting"],"source_type":"user_import",
 "source_reference":"test","license_id":"TEST_ONLY"}}
 r=c.post("/api/acquisition/translate",json=p)
 assert r.status_code==200 and r.json()["valid"]
