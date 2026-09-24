"""Deterministic catalogue page composition.

AI output is accepted only as an already approved creative asset reference.
Exact text, identifiers, page numbers and brand assets are composed by code.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from html import escape
import json

@dataclass(frozen=True)
class ComposedPage:
    html: bytes
    sha256: str
    manifest: dict


def _e(value):return escape(str(value if value is not None else ""),quote=True)

def compose_product_page(*, page_number:int, product:dict, master_visual:dict,
                         brand:dict, locale:str="en-GB") -> ComposedPage:
    if page_number<1:raise ValueError("page_number must be positive")
    if not product.get("product_id") or not product.get("display_name"):
        raise ValueError("canonical product_id and display_name are required")
    if master_visual.get("state") not in {"LOCKED","APPROVED"}:
        raise ValueError("page composition requires locked Master Visual")
    if not master_visual.get("sha256"):raise ValueError("Master Visual hash is required")
    logo=brand.get("logo_uri")
    logo_hash=brand.get("logo_sha256")
    if not logo or not logo_hash:raise ValueError("approved immutable logo asset is required")
    fields={
      "page_number":page_number,"product_id":product["product_id"],
      "variant_id":product.get("variant_id"),"display_name":product["display_name"],
      "description":product.get("description") or "",
      "master_visual_uri":master_visual.get("uri") or "",
      "master_visual_sha256":master_visual["sha256"],
      "logo_uri":logo,"logo_sha256":logo_hash,"locale":locale
    }
    html=("<!doctype html><html><head><meta charset=\"utf-8\"><title>"+
      _e(fields["display_name"])+"</title></head><body data-page=\""+str(page_number)+"\">"+
      "<header><img class=\"brand-logo\" src=\""+_e(logo)+"\" data-sha256=\""+_e(logo_hash)+"\"></header>"+
      "<main><img class=\"product-visual\" src=\""+_e(fields["master_visual_uri"])+"\" data-sha256=\""+
      _e(fields["master_visual_sha256"])+"\"><h1>"+_e(fields["display_name"])+"</h1>"+
      "<p class=\"product-id\">"+_e(fields["product_id"])+"</p>"+
      ("<p class=\"variant-id\">"+_e(fields["variant_id"])+"</p>" if fields["variant_id"] else "")+
      "<div class=\"description\">"+_e(fields["description"])+"</div></main>"+
      "<footer><span class=\"page-number\">"+str(page_number)+"</span></footer></body></html>")
    data=html.encode("utf-8")
    return ComposedPage(data,sha256(data).hexdigest(),fields)


def compose_interior_manifest(edition_id:int,pages:list[dict]) -> tuple[bytes,str]:
    payload={"schema":"opencrochet.catalogue.interior.v1","edition_id":edition_id,
             "pages":pages}
    data=json.dumps(payload,sort_keys=True,separators=(",",":")).encode("utf-8")
    return data,sha256(data).hexdigest()
