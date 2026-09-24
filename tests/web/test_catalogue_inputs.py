import base64

import pytest
from fastapi.testclient import TestClient

import src.web.app as appmod
from src.catalogue.ai_input import (
    CatalogueAIUnavailable,
    describe_product_photo,
    generate_catalogue_plan,
)
from src.catalogue.model_input import normalize_catalogue_model


def stored_products():
    return [
        {
            "id": 1,
            "name": "Fox",
            "description": "Crocheted fox toy with orange body and white muzzle.",
            "photo_url": "/media/product-photos/fox.png",
            "product_url": None,
            "materials": [{"yarn_id": "ORANGE", "yarn_brand": "Test", "yarn_product": "DK"}],
            "total_cost": 4.5,
            "total_cost_currency": "GBP",
            "updated_at": "2026-09-24T00:00:00+00:00",
        },
        {
            "id": 2,
            "name": "Bear",
            "description": "Brown crocheted bear toy.",
            "photo_url": None,
            "product_url": None,
            "materials": [],
            "total_cost": None,
            "total_cost_currency": None,
            "updated_at": "2026-09-24T00:00:00+00:00",
        },
    ]


def test_model_file_normalizes_stored_ids_and_standalone_product():
    m = normalize_catalogue_model(
        {"title": "Autumn", "product_ids": [2, 1], "include_materials": False},
        stored_products(),
    )
    assert m["schema"] == "opencrochet.catalogue.manifest.v1"
    assert [p["product_line_id"] for p in m["products"]] == [2, 1]
    assert m["options"]["include_materials"] is False
    assert m["generation"]["source"] == "model_file"

    one = normalize_catalogue_model(
        {
            "id": "external-model-42",
            "display_name": "Prototype rabbit",
            "description": "White rabbit with long ears.",
            "materials": [{"brand": "Example", "product": "DK", "quantity_g": 25}],
        },
        stored_products(),
    )
    assert one["products"][0]["product_line_id"] is None
    assert one["products"][0]["name"] == "Prototype rabbit"
    assert one["title"] == "Prototype rabbit"


def test_model_file_rejects_unknown_stored_id():
    with pytest.raises(ValueError, match="unknown stored product id 999"):
        normalize_catalogue_model({"product_ids": [999]}, stored_products())


def test_prompt_helper_accepts_only_known_ids_without_network():
    def transport(_body):
        return """{
          "title":"Fox collection",
          "subtitle":"Autumn",
          "locale":"en-GB",
          "format":"A4",
          "include_materials":true,
          "include_estimated_material_cost":false,
          "product_ids":[1],
          "product_copy":{"1":"Orange fox toy with a white muzzle."}
        }"""

    plan = generate_catalogue_plan(
        "Make a short fox catalogue",
        stored_products(),
        api_key="",
        model="test-model",
        _transport=transport,
    )
    assert plan["product_ids"] == [1]
    assert plan["product_copy"]["1"].startswith("Orange fox")

    with pytest.raises(CatalogueAIUnavailable, match="unknown product 999"):
        generate_catalogue_plan(
            "bad",
            stored_products(),
            api_key="",
            model="test-model",
            _transport=lambda _body: '{"title":"Bad","product_ids":[999]}',
        )


def test_product_photo_helper_uses_visible_description_only_transport():
    result = describe_product_photo(
        "image/png",
        b"fake-png-bytes",
        api_key="",
        model="test-model",
        _transport=lambda _body: '{"name":"Crocheted fox","description":"Orange fox-shaped toy with a white muzzle."}',
    )
    assert result["name"] == "Crocheted fox"
    assert "white muzzle" in result["description"]


def test_catalogue_prompt_endpoint_hydrates_real_records(monkeypatch):
    monkeypatch.setattr(appmod, "_catalogue_products_from_store", stored_products)
    monkeypatch.setattr(appmod, "_vision_settings", lambda: ("fake-key", "test-model"))
    monkeypatch.setattr(appmod, "vision_model_name", lambda _m: "test-model")
    monkeypatch.setattr(
        appmod,
        "generate_catalogue_plan",
        lambda *a, **k: {
            "title": "Prompt catalogue",
            "subtitle": "",
            "locale": "en-GB",
            "format": "A4",
            "include_materials": True,
            "include_estimated_material_cost": False,
            "product_ids": [1],
            "product_copy": {"1": "Catalogue copy from supplied fox facts."},
        },
    )
    client = TestClient(appmod.app)
    r = client.post("/api/catalogue/generate-from-prompt", json={"prompt": "Use the fox"})
    assert r.status_code == 200
    body = r.json()
    assert body["products"][0]["product_line_id"] == 1
    assert body["products"][0]["materials"][0]["yarn_id"] == "ORANGE"
    assert body["generation"]["source"] == "prompt"
    assert "fake-key" not in str(body)


def test_product_photo_upload_is_persistent_path_and_validated(monkeypatch, tmp_path):
    monkeypatch.setattr(appmod, "PRODUCT_PHOTO_DIR", tmp_path)
    client = TestClient(appmod.app)
    # 1x1 PNG
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    r = client.post("/api/admin/product-photo/upload", json={
        "media_type": "image/png",
        "data": base64.b64encode(png).decode("ascii"),
    })
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("/media/product-photos/") and url.endswith(".png")
    assert len(list(tmp_path.glob("*.png"))) == 1

    bad = client.post("/api/admin/product-photo/upload", json={
        "media_type": "text/plain",
        "data": base64.b64encode(b"x").decode("ascii"),
    })
    assert bad.status_code == 422


def test_shell_has_three_catalogue_inputs_photo_upload_and_hides_irrelevant_yarn_bar():
    html = TestClient(appmod.app).get("/").text
    for needle in (
        'id="catPrompt"',
        'id="catPromptGenerate"',
        'id="catModelFile"',
        'id="catModelLoad"',
        'id="lmPhotoFile"',
        'id="lmReadPhoto"',
        "function setYarnBarForTab(tab)",
        "['calc','patterns','yarns','stash','tools'].includes(tab)",
    ):
        assert needle in html, needle
    footer = html[html.index("async function loadCompanyFooter"):html.index("async function loadCompanyForm")]
    assert "c.address" not in footer
    assert "company_number" in footer
    assert 'id="coAddress"' not in html
    assert "$('coAddress')" not in html


def test_m124_shell_and_cache_version():
    client = TestClient(appmod.app)
    assert client.get("/api/health").json()["version"] == "M12.4"
    assert 'opencrochet-pro-m12-v6' in client.get("/sw.js").text
