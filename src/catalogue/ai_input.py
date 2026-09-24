"""AI helpers for catalogue prompt planning and product-photo description.

The model is allowed to arrange and rewrite only facts supplied by the application.
All model output is treated as untrusted input and validated before use.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_PROMPT_CHARS = 12_000


class CatalogueAIUnavailable(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    text = str(text or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise CatalogueAIUnavailable("the model did not return JSON")
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise CatalogueAIUnavailable(f"could not read the model response: {exc}") from exc
    if not isinstance(value, dict):
        raise CatalogueAIUnavailable("the model response must be a JSON object")
    return value


def _call_anthropic(content: list[dict], api_key: str, model: str, max_tokens: int,
                    timeout: int = 60, _transport=None) -> str:
    if _transport is not None:
        return str(_transport({
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}],
        }) or "")
    if not (api_key or "").strip():
        raise CatalogueAIUnavailable("AI generation is not configured")
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key.strip(),
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise CatalogueAIUnavailable(
            f"the AI service refused the request ({exc.code}): {detail}"
        ) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise CatalogueAIUnavailable(f"could not reach the AI service: {exc}") from exc
    return "".join(
        block.get("text", "")
        for block in payload.get("content", [])
        if block.get("type") == "text"
    )


def generate_catalogue_plan(prompt: str, products: list[dict], api_key: str, model: str,
                            _transport=None) -> dict:
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(f"prompt is too long (maximum {MAX_PROMPT_CHARS} characters)")
    available = {}
    compact = []
    for row in products:
        try:
            pid = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        available[pid] = row
        compact.append({
            "id": pid,
            "name": str(row.get("name") or "")[:200],
            "description": str(row.get("description") or "")[:1200],
            "materials": [
                {
                    "yarn": " ".join(filter(None, [
                        str(m.get("yarn_brand") or ""),
                        str(m.get("yarn_product") or m.get("yarn_id") or ""),
                    ])).strip(),
                    "length_m": m.get("length_m"),
                    "quantity_g": m.get("quantity_g"),
                }
                for m in (row.get("materials") or [])[:30]
            ],
            "estimated_material_cost": (
                None if row.get("total_cost") is None else {
                    "amount": row.get("total_cost"),
                    "currency": row.get("total_cost_currency"),
                }
            ),
        })
    if not compact:
        raise ValueError("no stored products are available")

    instruction = """Create a catalogue plan from the user's prompt and ONLY the product records provided below.
Return JSON only with:
{
  "title": "required catalogue title",
  "subtitle": "optional",
  "locale": "en-GB or cs-CZ",
  "format": "A4 or A4L",
  "include_materials": true/false,
  "include_estimated_material_cost": true/false,
  "product_ids": [ordered integer ids from the supplied records],
  "product_copy": {"<id>": "short catalogue copy based only on that product's supplied name/description"}
}
Rules:
- Never invent a product id, material, price, dimension, specification, manufacturer, certification or technical claim.
- Never change factual data. Product copy may rephrase only supplied text.
- Include at least one valid supplied product.
- If the user does not specify locale or format, use en-GB and A4.
"""
    content = [{
        "type": "text",
        "text": instruction + "\n\nPRODUCT RECORDS:\n" +
                json.dumps(compact, ensure_ascii=False, separators=(",", ":")) +
                "\n\nUSER PROMPT:\n" + prompt,
    }]
    raw = _extract_json(_call_anthropic(
        content, api_key, model, max_tokens=3000, _transport=_transport
    ))

    title = str(raw.get("title") or "").strip()[:200]
    if not title:
        raise CatalogueAIUnavailable("the generated catalogue has no title")
    locale = str(raw.get("locale") or "en-GB")
    if locale not in {"en-GB", "cs-CZ"}:
        locale = "en-GB"
    page_format = str(raw.get("format") or "A4").upper()
    if page_format not in {"A4", "A4L"}:
        page_format = "A4"
    raw_ids = raw.get("product_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raise CatalogueAIUnavailable("the generated catalogue did not select any products")
    ids = []
    for value in raw_ids:
        try:
            pid = int(value)
        except (TypeError, ValueError):
            raise CatalogueAIUnavailable("the generated catalogue contains an invalid product id")
        if pid not in available:
            raise CatalogueAIUnavailable(f"the generated catalogue referenced unknown product {pid}")
        if pid not in ids:
            ids.append(pid)
    copy_in = raw.get("product_copy") or {}
    product_copy = {}
    if isinstance(copy_in, dict):
        for pid in ids:
            text = copy_in.get(str(pid), copy_in.get(pid))
            if text:
                product_copy[str(pid)] = str(text).strip()[:1200]

    return {
        "title": title,
        "subtitle": str(raw.get("subtitle") or "").strip()[:300],
        "locale": locale,
        "format": page_format,
        "include_materials": bool(raw.get("include_materials", True)),
        "include_estimated_material_cost": bool(
            raw.get("include_estimated_material_cost", False)
        ),
        "product_ids": ids,
        "product_copy": product_copy,
    }


def describe_product_photo(media_type: str, blob: bytes, api_key: str, model: str,
                           _transport=None) -> dict:
    media_type = str(media_type or "").lower().strip()
    if media_type not in ALLOWED_MEDIA:
        raise ValueError("unsupported image type")
    if not blob:
        raise ValueError("photo is empty")
    if len(blob) > MAX_IMAGE_BYTES:
        raise ValueError("photo is too large (maximum 8 MB)")
    instruction = """Describe the visible product for a catalogue editor.
Return JSON only: {"name":"short visible-object name","description":"short factual description of what is visibly present"}.
Do not invent or infer materials, dimensions, price, model number, manufacturer, origin, certification, function not visible in the image, or any technical claim.
If something is uncertain, omit it. Do not write marketing claims."""
    content = [
        {"type": "image", "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.b64encode(blob).decode("ascii"),
        }},
        {"type": "text", "text": instruction},
    ]
    raw = _extract_json(_call_anthropic(
        content, api_key, model, max_tokens=1000, _transport=_transport
    ))
    name = str(raw.get("name") or "").strip()[:120]
    description = str(raw.get("description") or "").strip()[:1000]
    if not name and not description:
        raise CatalogueAIUnavailable("the model did not identify a usable product description")
    return {"name": name, "description": description}
