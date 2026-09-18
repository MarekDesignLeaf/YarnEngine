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


YARN_SPEC = {**SPEC, "yarn_diameter_mm": 2.5, "hook_mm": 3.5, "allowance_percent": 10}


def test_design_reports_yarn_length_per_part_and_in_total():
    d = c.post("/api/design/generate", json=YARN_SPEC).json()
    y = d["yarn"]
    assert y["available"] is True and y["length_m"] > 0
    head, arm = d["parts"]
    # a pair of arms costs twice one arm, and the total is the sum of the parts
    assert abs(arm["yarn"]["length_m_total"] - 2 * arm["yarn"]["length_m_each"]) < 0.05
    assert abs(y["length_m"] - (head["yarn"]["length_m_total"] + arm["yarn"]["length_m_total"])) < 0.05
    assert y["allowance_percent"] == 10


def test_design_yarn_matches_the_single_piece_calculator():
    # The designer must not disagree with the calculator about the same piece.
    d = c.post("/api/design/generate", json=YARN_SPEC).json()
    part = d["parts"][0]
    r = c.post("/api/complex-consumption/calculate", json={
        "program_type": "amigurumi",
        "program": {"initial_stitches": part["initial_stitches"], "rounds": part["rounds"]},
        "yarn_diameter_mm": 2.5, "hook_mm": 3.5,
        "gauge_stitches_per_10cm": SPEC["gauge_stitches_per_10cm"],
        "gauge_rows_per_10cm": SPEC["gauge_rows_per_10cm"],
        "allowance_percent": 10, "domain_policy": "warn"}).json()
    assert abs(part["yarn"]["length_m_each"] - r["calculation"]["recommended_length_m"]) < 0.01


def test_a_bigger_toy_needs_more_yarn():
    small = c.post("/api/design/generate", json={**YARN_SPEC, "total_height_cm": 12}).json()
    big = c.post("/api/design/generate", json={**YARN_SPEC, "total_height_cm": 30}).json()
    assert big["yarn"]["length_m"] > small["yarn"]["length_m"] * 2


def test_weight_and_balls_come_from_the_chosen_yarn():
    yarns = c.get("/api/yarns").json()
    rows = yarns if isinstance(yarns, list) else yarns.get("items", [])
    pick = next(y for y in rows if y.get("tex") and y.get("package_length_m"))
    d = c.post("/api/design/generate", json={**SPEC, "yarn_id": pick["yarn_id"],
                                             "hook_mm": 3.5, "allowance_percent": 10}).json()
    y = d["yarn"]
    assert y["mass_g"] > 0 and y["packages"] >= 1
    assert y["package_length_m"] == pick["package_length_m"]
    assert all(p["yarn"]["mass_g_total"] > 0 for p in d["parts"])
    assert f"{y['length_m']} m" in d["written"] and "YARN NEEDED" in d["written"]


def test_without_a_yarn_the_pattern_still_works_and_says_why():
    d = c.post("/api/design/generate", json=SPEC).json()
    assert d["yarn"]["available"] is False and "yarn" in d["yarn"]["reason"]
    assert d["parts"][0]["rounds"]          # the pattern itself is unaffected
    assert "YARN NEEDED" not in d["written"]
