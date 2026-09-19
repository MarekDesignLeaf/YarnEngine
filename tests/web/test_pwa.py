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
    assert ".round:nth-child(even){background:var(--round-alt)}" in html


def test_a_round_is_small_enough_to_see_whole():
    """A box round every round is no use if one round fills the screen.

    Each round carries a typed line, two pickers, a count, two buttons, a
    stitches-in/out row and a diagram. All of it open at once is a whole phone
    screen per round, so the boxes stop reading as separate rows — you never
    see two at a time. A round shows what it says; it opens its pickers when
    you touch it, which is the same touch that points it out on the shape.
    """
    html = c.get("/").text
    assert ".roundEdit{display:none" in html
    assert ".round.marked .roundEdit{display:flex}" in html
    assert ".round:not(.marked)>.roundDel{display:none}" in html   # and cannot be deleted by a slip
    assert ".round:not(.marked) .roundViz svg{width:56px" in html  # the diagram shrinks with it
    # the typed line and the diagram are what a closed round shows
    row = html[html.index("function roundRow(i,ops"):html.index("/* Set what a round ends with")]
    assert row.index('class="roundLine"') < row.index("roundViz(ops,outSt") < row.index('class="roundEdit"')


def test_row_one_is_how_the_piece_starts():
    """The editor, the written pattern and the make-mode agree on the number of
    every round — and on what row one is, which the construction decides."""
    html = c.get("/").text
    assert "function ringRow(initial)" in html
    assert "startLabel()" in html                                # named by the construction
    assert '<span class="pill">${i+2}</span>' in html            # the rest start at two
    assert "#rounds .round:not(.ring)" in html                   # and the start is not one of them
    closed = c.post("/api/crochet/amigurumi/written",
                    json={"initial_stitches": 6, "rounds": [{"operations": {"SC_INC": 6}}]}).json()
    assert closed["lines"][0] == "R1: 6 sc in magic ring (6)"
    assert closed["lines"][1].startswith("R2:")
    flat = c.post("/api/crochet/amigurumi/written",
                  json={"initial_stitches": 30, "construction": "flat_rows",
                        "rounds": [{"operations": {"SC": 30}}]}).json()
    assert flat["lines"][0].startswith("Row 1: ch 31")
    assert "across" in flat["lines"][1] and "around" not in flat["lines"][1]
    assert any("Turning chains" in n for n in flat["notes"])


def test_a_round_reads_in_the_order_a_pattern_says_it():
    """Stitch, then "x", then how many times — with the abbreviation first, so a
    narrow dropdown still shows the part that names the stitch."""
    html = c.get("/").text
    seg = html[html.index("function opSegHTML"):html.index("function ringRow")]
    assert seg.index("opSelectHTML(op)") < seg.index('class="opx"') < seg.index('class="opCount"')
    assert seg.index('class="opCount"') < seg.index('class="stepPair"') < seg.index('class="segDel"')
    assert "SC_INC:'inc'" in html and "SC:'sc'" in html
    assert "${a} — ${name}" in html
    assert ".op-seg .segDel{margin-left:auto" in html


def test_a_stitch_and_its_shaping_are_chosen_separately():
    """A maker picks the stitch, then says whether it is worked plain, as an
    increase or as a decrease — and only the combinations the engine has."""
    html = c.get("/").text
    assert "const OP_BUILD={" in html
    assert "SC:{none:'SC',inc:'SC_INC',dec:'SC2TOG',tog3:'SC3TOG'}" in html
    assert "TR:{none:'TR'}" in html            # no treble decrease is offered
    assert "none:'— worked plain —'" in html.replace("'none':", "none:")
    assert 'class="opBase"' in html and 'class="opShape"' in html
    assert "function opFromParts(base,shape)" in html


def test_each_round_shows_itself_as_a_picture():
    html = c.get("/").text
    assert "function roundViz(ops,outSt,hint)" in html
    assert "function evenSequence(ops)" in html          # shaping spread as it is worked
    assert "${roundViz(ops,outSt,i===0)}" in html        # drawn inside the round's own box
    assert ".roundViz .vzInc{fill:var(--good)}" in html


def test_the_round_you_touched_is_pointed_out_on_the_shape():
    """A ring drawn at exactly the surface radius is *in* the surface: half of
    it is buried and the slope hides the rest, so the round shows as a sliver
    at the silhouette and nothing else. It has to sit proud of the piece."""
    html = c.get("/").text
    assert "const radius = Math.max(0.1, point.x) + tube * 1.1" in html
    assert "const make = (through) =>" in html            # solid in front, ghosted behind
    assert "depthTest: !through" in html
    assert "function dropHighlight()" in html             # a group has to be disposed of by walking it
    assert "function markRound(index){" in html
    assert ".round.marked{border-color:var(--accent2)" in html


def test_which_end_of_the_shape_round_one_is_at_is_the_makers_choice():
    """A pattern is read from round 1 downwards, so by default the piece hangs
    from its first round and grows down the screen in the order the rounds are
    listed. Some people picture their work standing on its magic ring instead,
    so it is a switch rather than a decision made for them — and it sticks."""
    html = c.get("/").text
    assert 'id="ami3dFlip"' in html
    assert "function setOrder(topFirst)" in html
    assert "mesh.rotation.x = ringOnTop ? Math.PI : 0" in html   # a turn, never a scale of -1
    assert "meshOffsetY = ringOnTop ? meshMidY : -meshMidY" in html
    # the band goes with the piece when it is turned over
    assert "meshOffsetY + (ringOnTop ? -point.y : point.y)" in html
    assert "localStorage.setItem('ye_ring_top'" in html
    assert "localStorage.getItem('ye_ring_top')!=='bottom'" in html
    # and it says "Row 1" over a blanket, not "Round 1"
    assert "rowWord()==='row'?'Row':'Round'" in html


def test_the_editor_asks_how_the_piece_is_built():
    """The same engine costs a bear and a blanket; the editor has to ask which,
    because a stitch count means a different thing in each."""
    html = c.get("/").text
    assert 'id="construction"' in html and "How is this piece built?" in html
    assert "const CONSTRUCTION_TEMPLATES={" in html
    assert "round_open:[['tube','Straight tube']" in html
    assert "flat_rows:[['rect','Rectangle']" in html
    # the words follow the construction rather than assuming a toy
    assert "$('roundsHeading').textContent=word==='row'?'Rows':'Rounds'" in html
    assert "grows?'Widest stitch count':`How many ${word}s`" in html
    assert 'construction:($("construction").value||"round_closed")' in html
