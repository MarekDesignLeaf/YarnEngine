from fastapi.testclient import TestClient
from src.web.app import app
client=TestClient(app)
def test_operations_endpoint():
    r=client.get("/api/operations")
    assert r.status_code==200
    assert any(x["operation_id"]=="K" for x in r.json())
def test_editor_validate_valid_grid():
    payload={"pattern_id":"TEST_EDITOR","version":"1.0.0","name":"Editor Test","width":2,"height":2,
             "cells":[
               {"row":1,"col":1,"operation_id":"K","span":1},{"row":1,"col":2,"operation_id":"P","span":1},
               {"row":2,"col":1,"operation_id":"P","span":1},{"row":2,"col":2,"operation_id":"K","span":1}]}
    r=client.post("/api/editor/validate",json=payload)
    assert r.status_code==200
    assert r.json()["valid"] is True
def test_editor_validate_gap():
    payload={"pattern_id":"TEST_EDITOR","version":"1.0.0","name":"Editor Test","width":2,"height":1,
             "cells":[{"row":1,"col":1,"operation_id":"K","span":1}]}
    r=client.post("/api/editor/validate",json=payload)
    assert r.status_code==200
    assert r.json()["valid"] is False
