from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_pwa_assets():
 assert c.get("/").status_code==200
 m=c.get("/manifest.webmanifest");assert m.status_code==200 and m.json()["display"]=="standalone"
 s=c.get("/sw.js");assert s.status_code==200 and "Service-Worker-Allowed" in s.headers
 assert 'name="viewport"' in c.get("/").text
