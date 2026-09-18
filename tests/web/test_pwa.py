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

def test_ios_install_assets_are_served():
 # iOS ignores the manifest's icons and never prompts to install, so it needs a
 # PNG apple-touch-icon plus the apple-mobile-web-app tags for Add to Home Screen.
 page=c.get("/").text
 assert 'rel="apple-touch-icon"' in page
 assert 'name="apple-mobile-web-app-capable"' in page
 assert 'name="apple-mobile-web-app-title"' in page
 icon=c.get("/static/apple-touch-icon.png")
 assert icon.status_code==200 and icon.headers["content-type"]=="image/png"
 assert icon.content[:8]==b"\x89PNG\r\n\x1a\n"

def test_manifest_icons_are_png_for_launcher_support():
 icons=c.get("/manifest.webmanifest").json()["icons"]
 pngs=[i for i in icons if i["type"]=="image/png"]
 assert {i["sizes"] for i in pngs} >= {"192x192","512x512"}
 assert any(i["purpose"]=="maskable" for i in pngs)
 for i in icons:
  r=c.get(i["src"]); assert r.status_code==200, i["src"]

def test_head_root_serves_etag_for_the_in_page_version_check():
 # The page polls HEAD / and compares ETags to offer "Update now" when a
 # newer deploy is live, so HEAD must work and carry an ETag.
 r=c.head("/")
 assert r.status_code==200
 assert r.headers.get("etag")
 assert r.headers.get("cache-control")=="no-cache"


def test_the_yarn_bar_back_button_and_3d_toggle_are_in_the_shell():
    html = c.get("/").text
    for needle in ('id="yarnBar"', 'id="ybSwatch"', 'id="ybSpecs"',
                   'id="btnBack"', 'id="btn3d"', 'id="yarnColour"',
                   'id="photoOverlay"', 'id="dsgExplode"'):
        assert needle in html, needle


def test_colour_is_chosen_from_a_list_and_never_typed_in():
    html = c.get("/").text
    # the picker is a <select> fed from /api/colours; no free-text colour field
    assert '<select id="yarnColour">' in html
    assert "/api/colours" in html
