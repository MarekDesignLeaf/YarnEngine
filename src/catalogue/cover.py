"""Deterministic cover builder.

A cover is built only after the interior is locked. Product imagery, when used,
must come from approved catalogue assets. Exact brand and text elements are
composed by code.
"""
from __future__ import annotations
from hashlib import sha256
from html import escape
from pathlib import Path


def _e(v): return escape(str(v if v is not None else ""), quote=True)


class CoverBuilder:
    def __init__(self, store, output_root:Path):
        self.store=store
        self.output_root=Path(output_root)

    def build(self, edition_id:int, brand:dict, actor:str|None, product_asset_id:int|None=None):
        edition=self.store.get(edition_id)
        if not edition: raise KeyError("catalogue edition not found")
        if edition["state"]!="INTERIOR_LOCKED":
            raise ValueError("cover can be built only after INTERIOR_LOCKED")
        logo=brand.get("logo_uri"); logo_hash=brand.get("logo_sha256")
        if not logo or not logo_hash: raise ValueError("approved immutable logo asset is required")
        visual=None
        if product_asset_id is not None:
            visual=self.store.get_asset(int(product_asset_id))
            if not visual or visual["edition_id"]!=edition_id:
                raise ValueError("cover product asset does not belong to edition")
            if visual["asset_type"] not in {"MASTER_VISUAL","PRODUCT_VIEW","CANONICAL_3D"}:
                raise ValueError("cover product asset type is not permitted")
            if visual["state"] not in {"LOCKED","APPROVED","VALIDATED"}:
                raise ValueError("cover product asset must be approved or locked")
        title=_e(edition["title"]); subtitle=_e(edition.get("subtitle") or "")
        image=("" if not visual else
          '<img class="cover-product" src="'+_e(visual.get("uri") or "")+
          '" data-sha256="'+_e(visual.get("sha256") or "")+'" alt="">')
        html=(
          '<!doctype html><html><head><meta charset="utf-8"><title>'+title+
          '</title><style>html,body{margin:0;width:100%;height:100%;font-family:Arial,sans-serif}'
          '.cover{box-sizing:border-box;min-height:100vh;padding:10%;display:grid;place-items:center;text-align:center}'
          '.brand-logo{max-width:38%;max-height:90px}.cover-product{max-width:62%;max-height:52vh;object-fit:contain}'
          'h1{font-size:44px;margin:28px 0 8px}p{font-size:20px}</style></head><body><main class="cover">'+
          '<img class="brand-logo" src="'+_e(logo)+'" data-sha256="'+_e(logo_hash)+'" alt="">'+
          image+'<h1>'+title+'</h1>'+('<p>'+subtitle+'</p>' if subtitle else '')+
          '</main></body></html>')
        data=html.encode("utf-8"); digest=sha256(data).hexdigest()
        out=self.output_root/str(edition_id);out.mkdir(parents=True,exist_ok=True)
        path=out/"cover.html";path.write_bytes(data)
        asset=self.store.create_asset(edition_id,"COVER",None,str(path),digest,actor,{
          "composer":"deterministic-cover-v1","logo_sha256":logo_hash,
          "product_asset_id":visual["id"] if visual else None
        })
        if visual:
            self.store.add_dependency(edition_id,"ASSET",visual["id"],str(visual["version"]),"ASSET",asset["id"])
        return asset
