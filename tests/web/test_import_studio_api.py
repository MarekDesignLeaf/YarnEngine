from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def payload(pid="API_IMPORT_TEST"):
 return {"pattern":{"pattern_id":pid,"version":"1.0.0","name":"API Import","repeat":{"width_stitches":1,"height_rows":1},
 "rows":[{"row":1,"side":"RS","sequence":[{"op":"K","n":1}]}]},"metadata":{"family_id":"PLAIN","tags":["test"],"difficulty":"basic",
 "techniques":["knitting"],"source_type":"user_import","source_reference":"test-suite","license_id":"TEST_ONLY"}}
def test_inspect():
 r=c.post("/api/import-studio/inspect",json=payload());assert r.status_code==200 and r.json()["valid"]
def test_batch_limit_and_inspect():
 r=c.post("/api/import-studio/batch-inspect",json=[payload("B1"),payload("B2")]);assert r.status_code==200 and r.json()["total"]==2
