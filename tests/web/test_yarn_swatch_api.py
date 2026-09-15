from fastapi.testclient import TestClient
from src.web.app import app
client=TestClient(app)
def test_create_yarn_and_swatch():
 y={"yarn_id":"API_REAL_TEST","brand":"Test Brand","product":"Test Product","variant":None,"cyc_weight":4,
 "package_mass_g":100,"package_length_m":200,"fibre_composition":{"Wool":100},"nominal_diameter_mm":1.2}
 # tolerate previous local test residue
 r=client.post("/api/yarns",json=y)
 assert r.status_code in (200,409)
 s={"name":"Measured API swatch","pattern_id":"STOCKINETTE","pattern_version":"1.0.0","yarn_id":"API_REAL_TEST",
 "needle_mm":4,"stitches":20,"rows":28,"width_cm":10,"height_cm":10,"yarn_length_m":8}
 r=client.post("/api/swatches",json=s);assert r.status_code==200
 sid=r.json()["swatch_id"]
 assert client.get(f"/api/swatches/{sid}").status_code==200
 assert client.delete(f"/api/swatches/{sid}").status_code==200
