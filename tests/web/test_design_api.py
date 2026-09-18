import base64

from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)

SPEC = {
    "object": "teddy bear", "total_height_cm": 22,
    "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
    "parts": [
        {"name": "Head", "category": "HEAD", "height_fraction": 0.34, "width_fraction": 0.34},
        {"name": "Arm", "category": "LIMB", "height_fraction": 0.28, "width_fraction": 0.09, "copies": 2},
    ],
}


def test_status_reports_whether_photo_analysis_is_available():
    b = c.get("/api/design/status").json()
    assert isinstance(b["vision_configured"], bool)
    assert "sphere" in b["archetypes"] and "HEAD" in b["categories"]


def test_generate_returns_a_pattern_for_every_part():
    r = c.post("/api/design/generate", json=SPEC)
    assert r.status_code == 200
    d = r.json()
    assert [p["name"] for p in d["parts"]] == ["Head", "Arm"]
    assert d["piece_count"] == 3
    head = d["parts"][0]
    assert head["rounds"] and head["round_count"] == len(head["rounds"]) + 1
    assert head["written"][0].startswith("R1: 6 sc in magic ring")
    assert "HEAD — make 1" in d["written"]


def test_generated_rounds_are_accepted_by_the_round_analyser():
    d = c.post("/api/design/generate", json=SPEC).json()
    for part in d["parts"]:
        r = c.post("/api/crochet/amigurumi/analyse",
                   json={"initial_stitches": part["initial_stitches"], "rounds": part["rounds"]})
        assert r.status_code == 200 and r.json()["valid"], (part["name"], r.json())


def test_generated_rounds_can_be_costed_in_yarn():
    d = c.post("/api/design/generate", json=SPEC).json()
    part = d["parts"][0]
    r = c.post("/api/complex-consumption/calculate", json={
        "program_type": "amigurumi",
        "program": {"initial_stitches": part["initial_stitches"], "rounds": part["rounds"]},
        "yarn_diameter_mm": 2.5, "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
        "allowance_percent": 10, "domain_policy": "warn"})
    assert r.status_code == 200
    assert r.json()["calculation"]["recommended_length_m"] > 0


def test_generate_refuses_nonsense():
    assert c.post("/api/design/generate", json={**SPEC, "total_height_cm": 0}).status_code == 422
    assert c.post("/api/design/generate", json={**SPEC, "parts": []}).status_code == 422
    bad = {**SPEC, "parts": [{"name": "x", "archetype": "banana", "height_fraction": 0.5}]}
    assert c.post("/api/design/generate", json=bad).status_code == 422


def test_photo_endpoint_requires_a_photo():
    assert c.post("/api/design/from-photo", json={"total_height_cm": 20}).status_code == 422
    r = c.post("/api/design/from-photo", json={
        "total_height_cm": 20, "images": [{"media_type": "image/png", "data": "not base64!!"}]})
    assert r.status_code == 422


def test_photo_endpoint_says_so_when_analysis_is_not_configured(monkeypatch):
    # No API key set: the request must report that clearly (503) rather than
    # inventing a pattern.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()
    r = c.post("/api/design/from-photo", json={
        "total_height_cm": 20, "images": [{"media_type": "image/png", "data": png}]})
    assert r.status_code == 503
    assert "not set up" in r.json()["detail"].lower()


def test_photo_analysis_is_rate_limited_because_it_costs_money(monkeypatch):
    from src.web import app as app_mod
    monkeypatch.setattr(app_mod, "PHOTO_MAX_PER_HOUR", 2)
    app_mod._photo_calls.clear()
    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()
    body = {"total_height_cm": 20, "images": [{"media_type": "image/png", "data": png}]}
    codes = [c.post("/api/design/from-photo", json=body).status_code for _ in range(3)]
    assert codes[-1] == 429, codes          # third call in the window is refused
    app_mod._photo_calls.clear()
