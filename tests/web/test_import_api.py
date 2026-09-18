"""Importing a pattern over the API, and being honest about what cannot be."""
import base64

from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)

PATTERN = """HEAD
Round 1: Work 6 single crochet into a magic ring (6)
Round 2: 2 sc in each st around (12)
R3: [sc, inc] x 6 (18)
R4-6: sc in each st around (18)
Rnd 7: *sc, dec; rep from * around (12)
Fasten off."""


def test_pasted_text_comes_back_as_rounds_the_app_can_use():
    d = c.post("/api/import/rounds", json={"text": PATTERN}).json()
    assert d["valid"] is True and d["initial_stitches"] == 6
    assert len(d["rounds"]) == 6
    assert d["written"][0] == "R1: 6 sc in magic ring (6)"
    assert d["written"][-1] == "R7: [sc, dec] x 6 (12)"
    # and the rounds it produced pass the same validator the editor uses
    r = c.post("/api/crochet/amigurumi/analyse",
               json={"initial_stitches": d["initial_stitches"], "rounds": d["rounds"]})
    assert r.json()["valid"] is True


def test_the_imported_rounds_can_be_costed_straight_away():
    d = c.post("/api/import/rounds", json={"text": PATTERN}).json()
    r = c.post("/api/complex-consumption/calculate", json={
        "program_type": "amigurumi",
        "program": {"initial_stitches": d["initial_stitches"], "rounds": d["rounds"]},
        "yarn_id": "YARNSMITHS_DK", "hook_mm": 3.0, "gauge_stitches_per_10cm": 20,
        "gauge_rows_per_10cm": 22, "allowance_percent": 10, "domain_policy": "warn"})
    assert r.status_code == 200 and r.json()["calculation"]["recommended_length_m"] > 0


def test_unreadable_lines_are_listed_and_left_out():
    d = c.post("/api/import/rounds", json={
        "text": "R1: 6 sc in magic ring (6)\nR2: work a fancy puff thing around\nR3: inc in each st around (12)"}).json()
    assert [i["line"] for i in d["issues"]] == [2]
    assert "could not read" in d["issues"][0]["reason"]
    assert d["rounds"], "the readable rounds still came through"


def test_empty_and_oversized_text_are_refused():
    assert c.post("/api/import/rounds", json={"text": "   "}).status_code == 422
    assert c.post("/api/import/rounds", json={"text": "R1: 6 sc in magic ring\n" * 20000}).status_code == 422


def test_a_text_file_is_read():
    data = base64.b64encode(PATTERN.encode()).decode()
    d = c.post("/api/import/file", json={"filename": "head.txt", "data": data}).json()
    assert d["valid"] is True and d["source"] == "head.txt"


def test_a_pdf_of_pictures_says_so_instead_of_returning_nothing():
    # a valid but text-free PDF
    import pdfplumber  # noqa: F401  - the reader the endpoint uses
    blank = base64.b64encode(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"trailer<</Root 1 0 R>>").decode()
    r = c.post("/api/import/file", json={"filename": "scan.pdf", "data": blank})
    assert r.status_code == 422
    assert "pictures of the pages" in r.json()["detail"] or "could not be read" in r.json()["detail"]


def test_the_app_says_plainly_where_a_pattern_cannot_come_from():
    sources = {s["id"]: s for s in c.get("/api/import/sources").json()["sources"]}
    assert sources["text"]["available"] and sources["file"]["available"]
    for blocked in ("link", "ravelry", "youtube"):
        assert sources[blocked]["available"] is False
        assert sources[blocked]["note"]          # and says why, rather than failing later
    assert "copyright" in sources["link"]["note"]
