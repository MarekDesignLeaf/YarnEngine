"""The work log over the API, with two real accounts.

The point of these: a log is written without anyone asking for it, and one
person's work never shows up in another person's app unless they said so.
"""
import pytest
from fastapi.testclient import TestClient

import src.web.app as appmod
from src.worklog.store import WorkLogStore

AMI = {
    "program_type": "amigurumi",
    "program": {"initial_stitches": 6,
                "rounds": [{"operations": {"SC_INC": 6}}, {"operations": {"SC": 12}}]},
    "yarn_id": "YARNSMITHS_DK", "colour_id": "YARNSMITHS_DK__3208", "hook_mm": 3.0,
    "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
    "allowance_percent": 10, "domain_policy": "warn", "copies": 2,
    "title": "Bear head",
}


@pytest.fixture()
def team(monkeypatch, tmp_path):
    """Two signed-in people sharing one server, each with their own session."""
    monkeypatch.setenv("YARNENGINE_AUTH_DISABLED", "0")
    from src.web.auth import UserStore
    monkeypatch.setattr(appmod, "user_store", UserStore(tmp_path / "users.sqlite"))
    monkeypatch.setattr(appmod, "worklog_store", WorkLogStore(tmp_path / "worklog.sqlite"))
    marek = TestClient(appmod.app)
    marek.post("/api/auth/register", json={"username": "marek", "password": "correct-horse-1"})
    eva = TestClient(appmod.app)
    eva.post("/api/auth/register", json={"username": "eva", "password": "another-pass-22"})
    return marek, eva


def user_id(client, name):
    return next(c["user_id"] for c in client.get("/api/colleagues").json()["colleagues"]
                if c["username"] == name)


def test_a_calculation_writes_itself_into_the_log(team):
    marek, _ = team
    assert marek.get("/api/worklog").json()["entries"] == []
    r = marek.post("/api/complex-consumption/calculate", json=AMI)
    assert r.status_code == 200
    entries = marek.get("/api/worklog").json()["entries"]
    assert len(entries) == 1
    e = entries[0]
    assert e["title"] == "Bear head" and e["kind"] == "amigurumi"
    assert e["yarn_name"] == "Yarnsmiths Create DK"
    assert e["colour_name"] == "Bottle Green" and e["colour_hex"] == "#132a1a"
    assert e["pieces"] == 2 and e["length_m"] > 0 and e["mass_g"] > 0
    # the figures logged are the ones the calculation returned, doubled for the pair
    single = r.json()["calculation"]
    assert e["length_m"] == round(single["recommended_length_m"] * 2, 2)


def test_designing_from_parts_is_logged_too(team):
    marek, _ = team
    marek.post("/api/design/generate", json={
        "object": "teddy bear", "total_height_cm": 24,
        "gauge_stitches_per_10cm": 20, "gauge_rows_per_10cm": 22,
        "yarn_id": "YARNSMITHS_DK", "hook_mm": 3.0,
        "parts": [{"name": "Head", "category": "HEAD", "height_fraction": 0.34,
                   "width_fraction": 0.34}]})
    e = marek.get("/api/worklog").json()["entries"][0]
    assert e["kind"] == "design" and "teddy bear" in e["title"]
    assert e["stitches"] > 0 and e["length_m"] > 0


def test_pressing_calculate_twice_keeps_one_entry(team):
    marek, _ = team
    marek.post("/api/complex-consumption/calculate", json=AMI)
    marek.post("/api/complex-consumption/calculate", json=AMI)
    entries = marek.get("/api/worklog").json()["entries"]
    assert len(entries) == 1 and entries[0]["repeat_count"] == 2


def test_one_persons_log_is_not_another_persons_business(team):
    marek, eva = team
    marek.post("/api/complex-consumption/calculate", json=AMI)
    assert eva.get("/api/worklog").json()["entries"] == []          # her own log is empty
    assert eva.get("/api/worklog", params={"owner": user_id(eva, "marek")}).status_code == 403
    assert eva.get("/api/worklog/shares").json()["shared_with_me"] == []


def test_sharing_with_one_named_person_and_taking_it_back(team):
    marek, eva = team
    marek.post("/api/complex-consumption/calculate", json=AMI)
    eva_id = user_id(marek, "eva")
    assert marek.post("/api/worklog/shares", json={"user_id": eva_id}).status_code == 200
    assert [s["username"] for s in marek.get("/api/worklog/shares").json()["shared_with"]] == ["eva"]
    assert [o["username"] for o in eva.get("/api/worklog/shares").json()["shared_with_me"]] == ["marek"]

    marek_id = user_id(eva, "marek")
    seen = eva.get("/api/worklog", params={"owner": marek_id}).json()
    assert seen["owner"]["username"] == "marek" and seen["owner"]["is_me"] is False
    assert [e["title"] for e in seen["entries"]] == ["Bear head"]

    marek.delete(f"/api/worklog/shares/{eva_id}")
    assert eva.get("/api/worklog", params={"owner": marek_id}).status_code == 403


def test_a_private_entry_is_kept_back_from_the_people_you_share_with(team):
    marek, eva = team
    marek.post("/api/complex-consumption/calculate", json=AMI)
    marek.post("/api/complex-consumption/calculate",
               json={**AMI, "copies": 3, "title": "A client's own design"})
    marek.post("/api/worklog/shares", json={"user_id": user_id(marek, "eva")})
    secret = next(e for e in marek.get("/api/worklog").json()["entries"]
                  if e["title"] == "A client's own design")
    assert marek.patch(f"/api/worklog/{secret['entry_id']}",
                       json={"private": True}).status_code == 200
    marek_id = user_id(eva, "marek")
    titles = [e["title"] for e in eva.get("/api/worklog", params={"owner": marek_id}).json()["entries"]]
    assert titles == ["Bear head"]
    assert eva.get(f"/api/worklog/{secret['entry_id']}").status_code == 404


def test_notes_and_deletion_belong_to_the_owner_alone(team):
    marek, eva = team
    marek.post("/api/complex-consumption/calculate", json=AMI)
    marek.post("/api/worklog/shares", json={"user_id": user_id(marek, "eva")})
    entry = marek.get("/api/worklog").json()["entries"][0]
    assert eva.patch(f"/api/worklog/{entry['entry_id']}", json={"note": "hers"}).status_code == 404
    assert eva.delete(f"/api/worklog/{entry['entry_id']}").status_code == 404
    assert marek.patch(f"/api/worklog/{entry['entry_id']}",
                       json={"note": "order 214"}).json()["note"] == "order 214"
    assert marek.delete(f"/api/worklog/{entry['entry_id']}").status_code == 200
    assert marek.get("/api/worklog").json()["entries"] == []


def test_an_entry_can_be_reopened_with_everything_it_was_calculated_from(team):
    marek, _ = team
    marek.post("/api/complex-consumption/calculate", json=AMI)
    entry_id = marek.get("/api/worklog").json()["entries"][0]["entry_id"]
    full = marek.get(f"/api/worklog/{entry_id}").json()
    assert full["request"]["program"]["initial_stitches"] == 6
    assert full["request"]["yarn_id"] == "YARNSMITHS_DK"
    assert full["result"]["calculation"]["recommended_length_m"] > 0
    assert full["owner_username"] == "marek"


def test_the_people_you_can_share_with_are_named_and_nothing_more(team):
    marek, _ = team
    body = marek.get("/api/colleagues").json()
    assert [c["username"] for c in body["colleagues"]] == ["eva"]   # not myself
    assert set(body["colleagues"][0]) == {"user_id", "username", "role"}
