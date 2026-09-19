"""The tools over the API, including the promise the colour tool makes."""
from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)
GREEN = "YARNSMITHS_COTTONARAN__4183"          # Mojito Green, a real shade


# --- colour ---------------------------------------------------------------
def test_a_scheme_is_made_only_of_shades_that_can_be_ordered():
    d = c.get("/api/colours/palette", params={"colour_id": GREEN, "scheme": "complementary"}).json()
    card = {row["colour_id"] for row in
            c.get("/api/colours", params={"yarn_id": "YARNSMITHS_COTTONARAN"}).json()["colours"]}
    for entry in d["palette"]:
        assert entry["colour_id"] in card
        assert entry["code"] and entry["brand"] and entry["product"]
    assert d["palette"][0]["colour_id"] == GREEN


def test_the_colour_the_wheel_asked_for_is_shown_beside_the_one_that_exists():
    d = c.get("/api/colours/palette", params={"colour_id": GREEN, "scheme": "triadic"}).json()
    partner = d["palette"][1]
    assert partner["ideal_hex"] and partner["ideal_hex"] != partner["hex"]
    assert partner["distance"] > 0


def test_a_generic_palette_shade_is_refused_with_the_reason():
    r = c.get("/api/colours/palette", params={"colour_id": "PAL_WHT"})
    assert r.status_code == 422
    assert "can actually be bought" in r.json()["detail"]
    assert c.get("/api/colours/palette", params={"colour_id": "NOPE"}).status_code == 404


def test_the_scope_changes_how_many_real_shades_are_in_play():
    one_card = c.get("/api/colours/palette", params={"colour_id": GREEN, "scope": "yarn"}).json()
    whole = c.get("/api/colours/palette", params={"colour_id": GREEN, "scope": "library"}).json()
    assert whole["candidate_count"] > one_card["candidate_count"]
    assert c.get("/api/colours/palette",
                 params={"colour_id": GREEN, "scheme": "vibes"}).status_code == 422
    assert c.get("/api/colours/palette",
                 params={"colour_id": GREEN, "scope": "everywhere"}).status_code == 422


def test_the_toy_scheme_gives_a_body_a_muzzle_and_a_dark_detail():
    d = c.get("/api/colours/palette", params={"colour_id": GREEN, "scheme": "amigurumi"}).json()
    roles = [e["role"] for e in d["palette"]]
    assert roles[0] == "base"
    assert any("muzzle" in str(r) for r in roles) and any("eyes" in str(r) for r in roles)
    pale = next(e for e in d["palette"] if "muzzle" in str(e["role"]))
    body = d["palette"][0]
    pair = next(p for p in d["pairs"] if {p["a"], p["b"]} == {pale["name"], body["name"]})
    assert pair["contrast"] > 1.5, "a muzzle has to show up against the head"


def test_the_schemes_on_offer_explain_themselves():
    d = c.get("/api/colours/schemes").json()
    assert {s["id"] for s in d["schemes"]} >= {"complementary", "monochrome", "amigurumi"}
    assert all(s["about"] for s in d["schemes"])
    assert {s["id"] for s in d["scopes"]} == {"yarn", "brand", "stash", "library"}


# --- the small tools ------------------------------------------------------
def test_spreading_shaping_over_the_api():
    d = c.post("/api/tools/spread", json={"stitches": 50, "change": 6}).json()
    assert d["instruction"] == "[8 sc, inc] x 2, [7 sc, inc] x 4 (56)"
    # and what comes back is a round the editor can actually take
    analysed = c.post("/api/crochet/amigurumi/analyse",
                      json={"initial_stitches": 50, "rounds": [{"operations": d["operations"]}]})
    assert analysed.json()["valid"] is True
    assert c.post("/api/tools/spread", json={"stitches": 10, "change": -6}).status_code == 422
    assert c.post("/api/tools/spread",
                  json={"stitches": 36, "target": 48}).json()["to_stitches"] == 48


def test_sizes_and_conversions():
    d = c.post("/api/tools/size", json={"gauge_stitches_per_10cm": 20,
                                        "gauge_rows_per_10cm": 22, "width_cm": 25}).json()
    assert d["stitches"] == 50
    assert c.post("/api/tools/size", json={"gauge_stitches_per_10cm": 0,
                                           "width_cm": 25}).status_code == 422
    hooks = c.get("/api/tools/sizes").json()
    assert len(hooks["sizes"]) > 20 and "craftyarncouncil" in hooks["sources"]["metric_us"]["url"]
    assert c.get("/api/tools/sizes", params={"kind": "spoons"}).status_code == 422
    assert c.get("/api/tools/size-convert",
                 params={"mm": 4}).json()["size"]["us"] == "G-6"


def test_units_for_a_stated_ball():
    d = c.post("/api/tools/units", json={"yarn_id": "YARNSMITHS_COTTONARAN",
                                         "length_m": 120}).json()
    assert d["mass_g"] == 75.0 and "Cotton Aran" in d["yarn"]
    assert c.post("/api/tools/units", json={"value": 100, "unit": "m"}).json()["yards"] == 109.36
    assert c.post("/api/tools/units", json={"value": 1, "unit": "stones"}).status_code == 422


def test_a_blanket_plan_can_be_costed_by_the_engine():
    plan = c.post("/api/tools/squares", json={"width_cm": 120, "height_cm": 160,
                                              "square_cm": 15, "gauge_rows_per_10cm": 14}).json()
    assert plan["squares"] == plan["across"] * plan["down"]
    costed = c.post("/api/complex-consumption/calculate", json={
        "program_type": "amigurumi", "program": plan["program"],
        "yarn_id": "YARNSMITHS_COTTONARAN", "hook_mm": 4.0,
        "gauge_stitches_per_10cm": 14, "gauge_rows_per_10cm": 14,
        "allowance_percent": 10, "copies": plan["squares"], "domain_policy": "warn"})
    assert costed.status_code == 200
    assert costed.json()["calculation"]["recommended_length_m"] > 0


def test_a_swatch_is_saved_and_comes_back():
    before = len(c.get("/api/tools/gauges").json()["gauges"])
    assert c.post("/api/tools/gauges", json={"name": "Cotton Aran 3 mm",
                                             "stitches_per_10cm": 20, "rows_per_10cm": 22,
                                             "hook_mm": 3.0}).status_code == 200
    gauges = c.get("/api/tools/gauges").json()["gauges"]
    assert len(gauges) == before + 1
    assert c.post("/api/tools/gauges", json={"name": " ", "stitches_per_10cm": 20,
                                             "rows_per_10cm": 22}).status_code == 422
    assert c.post("/api/tools/gauges", json={"name": "x", "stitches_per_10cm": 0,
                                             "rows_per_10cm": 22}).status_code == 422
    mine = next(g for g in gauges if g["name"] == "Cotton Aran 3 mm")
    assert c.delete(f"/api/tools/gauges/{mine['id']}").status_code == 200
    assert c.delete("/api/tools/gauges/999999").status_code == 404


def test_a_price_is_built_on_what_the_piece_actually_took(tmp_path):
    """The point of tying this to the log: the yarn and the hours are real."""
    calc = c.post("/api/complex-consumption/calculate", json={
        "program_type": "amigurumi",
        "program": {"initial_stitches": 6,
                    "rounds": [{"operations": {"SC_INC": 6}},
                               {"operations": {"SC": 6, "SC_INC": 6}}]},
        "yarn_id": "YARNSMITHS_COTTONARAN", "hook_mm": 3.0,
        "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
        "allowance_percent": 10, "domain_policy": "warn"}).json()
    entry_id = calc["worklog_entry_id"]
    c.put(f"/api/worklog/{entry_id}/progress", json={"running": True})
    priced = c.post("/api/tools/price", json={
        "entry_id": entry_id, "hourly_rate": 12, "hours": 2.5,
        "price_per_package": 3.5, "margin_percent": 50}).json()
    assert priced["length_m"] > 0
    assert priced["labour"] == 30.0
    assert priced["yarn_cost"] is not None        # costed from the ball it actually uses
    assert priced["price"] > priced["cost"]
    assert round(priced["cost"] + priced["profit"], 2) == priced["price"]

    from_log = c.post("/api/tools/price", json={"entry_id": entry_id, "hourly_rate": 12}).json()
    assert from_log["time_from_log"] is True      # hours come from the clock when not given

    assert c.post("/api/tools/price", json={"entry_id": 999999}).status_code == 404
    assert c.post("/api/tools/price", json={}).status_code == 422
