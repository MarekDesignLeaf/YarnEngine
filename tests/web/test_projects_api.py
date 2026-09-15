from fastapi.testclient import TestClient
from src.web.app import app
client=TestClient(app)
def payload(name="Project API Test"):
    return {
      "name":name,
      "calculation":{
        "pattern_id":"STOCKINETTE","pattern_version":"1.0.0","yarn_id":None,
        "width_cm":20,"height_cm":20,"gauge_stitches_per_10cm":20,"gauge_rows_per_10cm":28,
        "allowance_percent":8,"partial_repeat_mode":"reject",
        "edges":{"left_stitches":0,"right_stitches":0,"left_operation":"K","right_operation":"K"},
        "calculation_mode":"swatch",
        "swatch":{"stitches":20,"rows":28,"yarn_length_m":8},
        "yarn_diameter_mm":None
      },
      "status":"draft"
    }
def test_project_crud():
    r=client.post("/api/projects",json=payload())
    assert r.status_code==200
    p=r.json(); pid=p["project_id"]
    assert client.get(f"/api/projects/{pid}").status_code==200
    u=client.put(f"/api/projects/{pid}",json={"name":"Updated"})
    assert u.status_code==200 and u.json()["name"]=="Updated"
    assert client.delete(f"/api/projects/{pid}").status_code==200
    assert client.get(f"/api/projects/{pid}").status_code==404
