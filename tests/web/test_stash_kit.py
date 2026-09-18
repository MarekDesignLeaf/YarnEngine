"""The rest of the kit: hooks, needles and the oddments a bag actually holds."""
from fastapi.testclient import TestClient

from src.web.app import app

c = TestClient(app)


def clear():
    for item in c.get("/api/stash/items").json()["items"]:
        c.delete(f"/api/stash/items/{item['id']}")


def test_a_hook_a_needle_and_an_oddment_each_have_a_place():
    clear()
    assert c.post("/api/stash/items", json={
        "kind": "hook", "name": "Clover Amour", "brand": "Clover",
        "size_mm": 3.0, "quantity": 2}).status_code == 200
    c.post("/api/stash/items", json={"kind": "needle", "name": "Bamboo straights",
                                     "size_mm": 4.0, "quantity": 1})
    c.post("/api/stash/items", json={"kind": "supply", "name": "Safety eyes 8 mm",
                                     "quantity": 40, "notes": "black"})
    body = c.get("/api/stash/items").json()
    assert body["counts"] == {"hook": 1, "needle": 1, "supply": 1, "tool": 0}
    assert [i["name"] for i in c.get("/api/stash/items", params={"kind": "hook"}).json()["items"]] \
        == ["Clover Amour"]
    clear()


def test_the_same_hook_added_twice_changes_the_count_not_the_list():
    clear()
    for quantity in (1, 3):
        c.post("/api/stash/items", json={"kind": "hook", "name": "Clover Amour",
                                         "size_mm": 3.0, "quantity": quantity})
    items = c.get("/api/stash/items", params={"kind": "hook"}).json()["items"]
    assert len(items) == 1 and items[0]["quantity"] == 3
    # a different size is a different hook, though
    c.post("/api/stash/items", json={"kind": "hook", "name": "Clover Amour", "size_mm": 3.5})
    assert len(c.get("/api/stash/items", params={"kind": "hook"}).json()["items"]) == 2
    clear()


def test_searching_the_kit():
    clear()
    c.post("/api/stash/items", json={"kind": "supply", "name": "Safety eyes 8 mm",
                                     "quantity": 40, "notes": "black"})
    c.post("/api/stash/items", json={"kind": "supply", "name": "Stitch markers", "quantity": 20})
    found = c.get("/api/stash/items", params={"q": "eyes"}).json()["items"]
    assert [i["name"] for i in found] == ["Safety eyes 8 mm"]
    assert c.get("/api/stash/items", params={"q": "black"}).json()["items"]      # notes too
    clear()


def test_nonsense_is_refused_rather_than_stored():
    assert c.post("/api/stash/items", json={"kind": "wand", "name": "x"}).status_code == 422
    assert c.post("/api/stash/items", json={"kind": "hook", "name": " "}).status_code == 422
    assert c.post("/api/stash/items",
                  json={"kind": "hook", "name": "x", "size_mm": 999}).status_code == 422
    assert c.post("/api/stash/items",
                  json={"kind": "hook", "name": "x", "quantity": -2}).status_code == 422
    assert c.get("/api/stash/items", params={"kind": "wand"}).status_code == 422


def test_deleting_something_that_is_not_yours_is_a_404():
    assert c.delete("/api/stash/items/999999").status_code == 404
