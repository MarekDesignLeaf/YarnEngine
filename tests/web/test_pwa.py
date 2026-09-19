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


def test_weight_says_what_is_missing_rather_than_showing_a_dash():
    html = c.get("/").text
    assert 'id="rMassNote"' in html and 'id="rMassLabel"' in html
    assert "needs a yarn" in html


def test_the_work_log_tab_and_sharing_are_in_the_shell():
    html = c.get("/").text
    for needle in ('data-tab="worklog"', 'id="tab-worklog"', 'id="wlTable"',
                   'id="wlShareList"', 'id="wlOwner"', 'id="pieceName"'):
        assert needle in html, needle


def test_the_yarn_bar_does_not_claim_things_that_are_not_true():
    html = c.get("/").text
    # one stated needle size is not a range, an empty swatch reads as empty,
    # the 3D switch only exists where the preview does, and "achieved size"
    # is a size rather than a round count
    assert "needle ${lo===hi||hi==null?lo:lo+'–'+hi} mm" in html
    assert ".yarnbar .swatch.empty" in html and "classList.toggle('empty'" in html
    assert "function amiFinishedSize(" in html
    assert "$('btn3d').classList.toggle('hidden',!applies)" in html


def test_the_phone_layout_guards_are_in_place():
    """One wide table used to stretch the whole app sideways on a phone; these
    are the rules that stop it, and they are easy to lose in a refactor."""
    html = c.get("/").text
    assert ".grid2>*,.toolGrid>*,.fields>*,.card{min-width:0}" in html
    assert ".tablewrap{max-height:58vh" in html          # the 200-row list scrolls itself
    assert "@media(max-width:520px){.fields,.fields.three{grid-template-columns:repeat(2" in html
    assert "input[type=checkbox],input[type=radio]{width:20px;height:20px" in html
    assert "body.has-install-bar{padding-bottom:104px}" in html


def test_a_row_is_visibly_one_row():
    """Cells wrap onto several lines, so rows need an outline of their own."""
    html = c.get("/").text
    assert "border-collapse:separate;border-spacing:0 5px" in html
    assert "tbody tr:nth-child(even){background:var(--row-alt)}" in html
    assert "tbody td:first-child{border-left:1px solid var(--line);border-radius:10px 0 0 10px}" in html
    assert "#wlTable,#yarnTable{table-layout:fixed}" in html      # a row cannot spill out
    assert ".round:nth-child(even){background:var(--row-alt)}" in html


def test_round_one_is_always_the_magic_ring():
    """The editor, the written pattern and the make-mode agree on the number of
    every round, because the ring is round one in all three."""
    html = c.get("/").text
    assert "function ringRow(initial)" in html
    assert ">magic ring<" in html
    assert '<span class="pill">${i+2}</span>' in html            # editable rounds start at two
    assert "#rounds .round:not(.ring)" in html                   # and the ring is not one of them
    written = c.post("/api/crochet/amigurumi/written",
                     json={"initial_stitches": 6, "rounds": [{"operations": {"SC_INC": 6}}]})
    assert written.json()["lines"][0] == "R1: 6 sc in magic ring (6)"
    assert written.json()["lines"][1].startswith("R2:")
