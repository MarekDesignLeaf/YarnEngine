from fastapi.testclient import TestClient
from src.web.app import app
c=TestClient(app)
def test_pwa_assets():
 assert c.get("/").status_code==200
 m=c.get("/manifest.webmanifest");assert m.status_code==200 and m.json()["display"]=="standalone"
 s=c.get("/sw.js");assert s.status_code==200 and "Service-Worker-Allowed" in s.headers
 assert 'name="viewport"' in c.get("/").text

def test_app_shell_forces_revalidation_so_deploys_are_picked_up():
 # Browsers were keeping an old copy of the app after deploys (heuristic
 # caching, since no Cache-Control was sent). The shell must revalidate.
 for path in ("/","/sw.js","/manifest.webmanifest","/static/index.html"):
  r=c.get(path)
  assert r.status_code==200,path
  assert r.headers.get("cache-control")=="no-cache",path

def test_head_root_serves_etag_for_the_in_page_version_check():
 # The page polls HEAD / and compares ETags to offer "Update now" when a
 # newer deploy is live, so HEAD must work and carry an ETag.
 r=c.head("/")
 assert r.status_code==200
 assert r.headers.get("etag")
 assert r.headers.get("cache-control")=="no-cache"
