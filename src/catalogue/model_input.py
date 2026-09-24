"""Normalize untrusted catalogue-model JSON into the OpenCrochet manifest shape."""
from __future__ import annotations


MAX_PRODUCTS = 500


def _text(value, limit):
    return str(value or "").strip()[:limit]


def _stored_product(row: dict, sequence: int, copy: str | None = None) -> dict:
    return {
        "sequence": sequence,
        "product_line_id": int(row["id"]),
        "name": _text(row.get("name"), 200),
        "description": _text(copy if copy is not None else row.get("description"), 2000) or None,
        "photo_url": _text(row.get("photo_url"), 2000) or None,
        "product_url": _text(row.get("product_url"), 2000) or None,
        "materials": list(row.get("materials") or [])[:100],
        "estimated_material_cost": (
            None if row.get("total_cost") is None else {
                "amount": row.get("total_cost"),
                "currency": _text(row.get("total_cost_currency"), 8) or None,
            }
        ),
        "source_updated_at": row.get("updated_at"),
    }


def _standalone_product(row: dict, sequence: int) -> dict:
    if not isinstance(row, dict):
        raise ValueError("each model product must be an object")
    name = _text(row.get("display_name") or row.get("name"), 200)
    if not name:
        raise ValueError("generated product model is missing display_name or name")
    materials = row.get("materials") or []
    if not isinstance(materials, list):
        raise ValueError("product materials must be a list")
    clean_materials = []
    for material in materials[:100]:
        if not isinstance(material, dict):
            continue
        clean_materials.append({
            "yarn_id": _text(material.get("yarn_id"), 120) or None,
            "yarn_brand": _text(material.get("yarn_brand") or material.get("brand"), 200) or None,
            "yarn_product": _text(material.get("yarn_product") or material.get("product"), 200) or None,
            "length_m": material.get("length_m"),
            "quantity_g": material.get("quantity_g"),
            "notes": _text(material.get("notes"), 1000) or None,
        })
    return {
        "sequence": sequence,
        "product_line_id": None,
        "name": name,
        "description": _text(row.get("description"), 2000) or None,
        "photo_url": _text(row.get("photo_url"), 2000) or None,
        "product_url": _text(row.get("product_url"), 2000) or None,
        "materials": clean_materials,
        "estimated_material_cost": None,
        "source_updated_at": None,
    }


def normalize_catalogue_model(raw: dict, stored_products: list[dict]) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("model file must contain a JSON object")
    stored = {}
    for row in stored_products:
        try:
            stored[int(row["id"])] = row
        except (KeyError, TypeError, ValueError):
            continue

    options = raw.get("options") if isinstance(raw.get("options"), dict) else {}
    title = _text(raw.get("title") or "Product Catalogue", 200)
    subtitle = _text(raw.get("subtitle"), 300)
    locale = _text(raw.get("locale") or "en-GB", 20)
    if locale not in {"en-GB", "cs-CZ"}:
        locale = "en-GB"
    page_format = _text(raw.get("format") or raw.get("page_format") or "A4", 10).upper()
    if page_format not in {"A4", "A4L"}:
        page_format = "A4"
    include_materials = bool(
        options.get("include_materials", raw.get("include_materials", True))
    )
    include_costs = bool(
        options.get(
            "include_estimated_material_cost",
            raw.get("include_estimated_material_cost", False),
        )
    )

    products = []
    raw_ids = raw.get("product_ids")
    if raw_ids is not None:
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValueError("product_ids must be a non-empty list")
        if len(raw_ids) > MAX_PRODUCTS:
            raise ValueError(f"model contains more than {MAX_PRODUCTS} products")
        for seq, value in enumerate(raw_ids, 1):
            try:
                pid = int(value)
            except (TypeError, ValueError):
                raise ValueError("invalid product id")
            if pid not in stored:
                raise ValueError(f"unknown stored product id {pid}")
            products.append(_stored_product(stored[pid], seq))
    elif "products" in raw:
        rows = raw.get("products")
        if not isinstance(rows, list) or not rows:
            raise ValueError("products must be a non-empty list")
        if len(rows) > MAX_PRODUCTS:
            raise ValueError(f"model contains more than {MAX_PRODUCTS} products")
        for seq, item in enumerate(rows, 1):
            if not isinstance(item, dict):
                raise ValueError("each product must be an object")
            # Only the explicit OpenCrochet product_line_id maps to the database.
            # A generated model may have its own unrelated "id" field.
            pid = item.get("product_line_id")
            if pid is not None:
                try:
                    pid = int(pid)
                except (TypeError, ValueError):
                    raise ValueError("invalid stored product id")
                if pid not in stored:
                    raise ValueError(f"unknown stored product id {pid}")
                copy = item.get("catalogue_copy")
                if copy is None and raw.get("schema") == "opencrochet.catalogue.manifest.v1":
                    copy = item.get("description")
                products.append(_stored_product(
                    stored[pid], seq, _text(copy, 2000) if copy is not None else None
                ))
            else:
                products.append(_standalone_product(item, seq))
    elif raw.get("display_name") or raw.get("name"):
        products = [_standalone_product(raw, 1)]
        if raw.get("title") is None:
            title = products[0]["name"]
    else:
        raise ValueError(
            "model must contain product_ids, products, or a product name/display_name"
        )

    if not products:
        raise ValueError("model contains no products")
    return {
        "schema": "opencrochet.catalogue.manifest.v1",
        "title": title or "Product Catalogue",
        "subtitle": subtitle,
        "locale": locale,
        "format": page_format,
        "options": {
            "include_materials": include_materials,
            "include_estimated_material_cost": include_costs,
        },
        "products": products,
        "generation": {"source": "model_file"},
    }
