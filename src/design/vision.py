"""Photo -> a description of the parts to crochet.

A vision model is asked one narrow question: what parts does this object have,
what basic shape is each one, and how big is each relative to the whole. It is
explicitly *not* asked for stitch counts, rounds or a pattern -- those are
computed from the gauge and the stated height by src.design.shapes, so the
numbers a person works from are always derived, reproducible and internally
consistent, whatever the model says.

Configured with one environment variable:

  ANTHROPIC_API_KEY        API key. If unset, photo analysis reports itself as
                           unavailable instead of failing at request time; the
                           rest of the designer (describing the parts yourself)
                           keeps working.
  YARNENGINE_VISION_MODEL  Model id to call. Defaults to a current Claude
                           vision model; override without a code change if the
                           account has a different one available.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

from .shapes import ARCHETYPES

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-4-5"
ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
CATEGORIES = ["HEAD", "BODY", "LIMB", "ARM", "LEG", "PAW_FOOT", "HAND", "EAR",
              "HORN_ANTLER", "TAIL", "MUZZLE", "NECK", "BEAK", "WING", "FIN",
              "SHELL_ARMOR", "ACCESSORY_BODY", "FACIAL_FEATURE"]

PROMPT = """You are helping plan a crochet amigurumi of the object in the photo(s).

Describe ONLY what you can see: which separate pieces the object would be made
from, the basic shape of each, and its size relative to the object's full
height. Do not give stitch counts, rounds, yarn amounts or any pattern text --
those are calculated separately from the maker's gauge.

Return ONLY a JSON object, no prose, no code fences:
{
  "object": "short name of the thing",
  "confidence": "high" | "medium" | "low",
  "parts": [
    {
      "name": "Head",
      "category": one of %(categories)s,
      "archetype": one of %(archetypes)s,
      "copies": integer, how many identical pieces are needed (2 for a pair),
      "height_fraction": part height as a fraction of the object's full height,
      "width_fraction": part width as a fraction of the object's full height,
      "colour": "short colour name as seen, or null",
      "stuffed": true/false
    }
  ],
  "assembly": ["short sewing/assembly notes, in order"],
  "uncertain": ["anything the photo does not show, e.g. the back, how it is joined"]
}

Rules:
- Every piece that is crocheted separately gets its own entry; a left and right
  of the same thing is ONE entry with copies: 2.
- Fractions are of the object's TOTAL height and must be > 0 and <= 1.5.
- Flat pieces (eye patches, soles) use archetype "disc" and stuffed false.
- If the object is a single piece, return one part.
- Be honest in "uncertain": a photo cannot show the inside, the back, or how
  pieces are joined.
""" % {"categories": CATEGORIES, "archetypes": sorted(ARCHETYPES)}


class VisionUnavailable(RuntimeError):
    """Photo analysis is not configured or could not be reached."""


def env_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def configured(stored_key: str | None = None) -> bool:
    return bool((stored_key or "").strip() or env_key())


def model_name(stored_model: str | None = None) -> str:
    return ((stored_model or "").strip()
            or os.environ.get("YARNENGINE_VISION_MODEL", "").strip()
            or DEFAULT_MODEL)


def mask_key(key: str | None) -> str | None:
    """What may be shown back to a browser: enough to recognise, not to use."""
    key = (key or "").strip()
    if not key:
        return None
    return f"{key[:7]}…{key[-4:]}" if len(key) > 14 else "…" + key[-2:]


def _extract_json(text: str) -> dict:
    """Pull the JSON object out of a model reply, tolerating stray prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise VisionUnavailable("the vision model did not return a description of the parts")
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise VisionUnavailable(f"could not read the vision model's answer: {e}") from e


def validate_parts(raw: dict) -> dict:
    """Keep only what we can actually build from, and say so when we drop things.

    The model's answer is untrusted input: anything outside the known shapes,
    categories and sensible proportions is rejected here rather than being fed
    into the pattern generator.
    """
    parts, dropped = [], []
    for p in (raw.get("parts") or []):
        try:
            name = str(p.get("name") or "").strip() or "Part"
            archetype = str(p.get("archetype") or "").strip().lower()
            category = str(p.get("category") or "").strip().upper()
            hf = float(p.get("height_fraction"))
            wf = float(p.get("width_fraction") or hf)
            copies = int(p.get("copies") or 1)
        except (TypeError, ValueError):
            dropped.append(str(p.get("name") if isinstance(p, dict) else p))
            continue
        if archetype not in ARCHETYPES or not (0 < hf <= 1.5) or not (0 < wf <= 1.5) or not (1 <= copies <= 20):
            dropped.append(name)
            continue
        parts.append({
            "name": name[:40],
            "category": category if category in CATEGORIES else None,
            "archetype": archetype,
            "copies": copies,
            "height_fraction": round(hf, 4),
            "width_fraction": round(wf, 4),
            "colour": (str(p.get("colour"))[:30] if p.get("colour") else None),
            "stuffed": bool(p.get("stuffed", True)),
        })
    if not parts:
        raise VisionUnavailable("no usable parts were identified in the photo")
    return {
        "object": str(raw.get("object") or "amigurumi")[:60],
        "confidence": raw.get("confidence") if raw.get("confidence") in ("high", "medium", "low") else "low",
        "parts": parts,
        "assembly": [str(x)[:200] for x in (raw.get("assembly") or [])][:12],
        "uncertain": [str(x)[:200] for x in (raw.get("uncertain") or [])][:12],
        "dropped": dropped,
    }


def describe_photo(images: list[tuple[str, bytes]], hint: str | None = None,
                   timeout: int = 60, api_key: str | None = None,
                   model: str | None = None, _transport=None) -> dict:
    """Ask the vision model what parts the pictured object is made of.

    images: (media_type, raw bytes) pairs. api_key/model come from the admin
    page when set there, falling back to the environment. _transport is for
    tests.
    """
    api_key = (api_key or "").strip() or env_key()
    if not api_key and _transport is None:
        raise VisionUnavailable(
            "photo analysis is not set up yet — an administrator can add an API key "
            "on the admin page")
    if not images:
        raise VisionUnavailable("no photo was supplied")
    content = []
    for media_type, blob in images[:4]:
        if media_type not in ALLOWED_MEDIA:
            raise VisionUnavailable(f"unsupported image type: {media_type}")
        if len(blob) > MAX_IMAGE_BYTES:
            raise VisionUnavailable("photo is too large (maximum 5 MB each)")
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": media_type,
            "data": base64.b64encode(blob).decode("ascii")}})
    text = PROMPT
    if hint:
        text += f"\n\nThe maker says this is: {str(hint)[:200]}"
    content.append({"type": "text", "text": text})

    chosen_model = model_name(model)
    body = {"model": chosen_model, "max_tokens": 2000,
            "messages": [{"role": "user", "content": content}]}
    if _transport is not None:
        raw_text = _transport(body)
    else:
        req = urllib.request.Request(
            API_URL, data=json.dumps(body).encode("utf-8"),
            headers={"x-api-key": api_key, "anthropic-version": API_VERSION,
                     "content-type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise VisionUnavailable(f"the vision service refused the request ({e.code}): {detail}") from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise VisionUnavailable(f"could not reach the vision service: {e}") from e
        raw_text = "".join(b.get("text", "") for b in payload.get("content", [])
                           if b.get("type") == "text")
    described = validate_parts(_extract_json(raw_text))
    described["model"] = chosen_model
    return described


TRANSCRIBE_PROMPT = """Transcribe the crochet pattern in these images as plain text.

Rules:
- Copy the round and row instructions exactly as written, one per line, keeping
  the round numbers, the abbreviations, the brackets and the stitch counts.
- Keep the part headings (HEAD, BODY, ARM) on their own lines.
- Do not translate abbreviations, do not convert between UK and US terms, do
  not tidy up the wording and do not fill in anything that is unclear.
- If a line is unreadable in the image, write it as [unreadable] rather than
  guessing what it said.
- Output the text only. No commentary, no summary, no code fences."""


def transcribe_pattern(images: list[tuple[str, bytes]], timeout: int = 60,
                       api_key: str | None = None, model: str | None = None,
                       _transport=None) -> str:
    """Read a photographed or scanned pattern back as text, verbatim.

    Deliberately a transcription and nothing more: the reading of what the
    stitches mean is done afterwards by src/pattern_import/crochet_rounds.py,
    which is deterministic and reports what it cannot read. A model that is
    asked to transcribe can be checked against the page; one asked to interpret
    cannot.
    """
    api_key = (api_key or "").strip() or env_key()
    if not api_key and _transport is None:
        raise VisionUnavailable(
            "reading a photographed pattern is not set up yet — an administrator "
            "can add an API key on the admin page")
    if not images:
        raise VisionUnavailable("no photo was supplied")
    content = []
    for media_type, blob in images[:4]:
        if media_type not in ALLOWED_MEDIA:
            raise VisionUnavailable(f"unsupported image type: {media_type}")
        if len(blob) > MAX_IMAGE_BYTES:
            raise VisionUnavailable("photo is too large (maximum 5 MB each)")
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": media_type,
            "data": base64.b64encode(blob).decode("ascii")}})
    content.append({"type": "text", "text": TRANSCRIBE_PROMPT})
    body = {"model": model_name(model), "max_tokens": 4000,
            "messages": [{"role": "user", "content": content}]}
    if _transport is not None:
        return str(_transport(body) or "").strip()
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode("utf-8"),
        headers={"x-api-key": api_key, "anthropic-version": API_VERSION,
                 "content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise VisionUnavailable(f"the vision service refused the request ({e.code}): {detail}") from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise VisionUnavailable(f"could not reach the vision service: {e}") from e
    return "".join(b.get("text", "") for b in payload.get("content", [])
                   if b.get("type") == "text").strip()
