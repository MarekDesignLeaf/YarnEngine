"""Responsive digital catalogue builder."""
from __future__ import annotations
from hashlib import sha256
from html import escape
from pathlib import Path
import json


def _e(v):return escape(str(v if v is not None else ""),quote=True)


class DigitalCatalogueBuilder:
    def __init__(self, store, output_root:Path):
        self.store=store;self.output_root=Path(output_root)

    def build(self, edition_id:int, actor:str|None):
        edition=self.store.get(edition_id)
        if not edition:raise KeyError("catalogue edition not found")
        products=edition["manifest"].get("products") or []
        assets=self.store.list_assets(edition_id)
        cards=[]
        for p in products:
            pid=int(p["product_line_id"])
            visuals=[a for a in assets if a["product_line_id"]==pid and
                     a["asset_type"] in {"MASTER_VISUAL","PRODUCT_VIEW"} and
                     a["state"] in {"LOCKED","APPROVED","VALIDATED"}]
            visual=next((a for a in visuals if a["asset_type"]=="MASTER_VISUAL"),visuals[0] if visuals else None)
            cards.append('<article id="product-'+str(pid)+'" class="product">'+
              (('<img loading="lazy" src="'+_e(visual.get("uri") or "")+'" alt="">') if visual else '')+
              '<div><h2>'+_e(p.get("name") or "")+'</h2><p>'+_e(p.get("description") or "")+'</p>'+
              (('<a href="'+_e(p.get("product_url"))+'">Product link</a>') if p.get("product_url") else '')+
              '</div></article>')
        html=('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+
          '<title>'+_e(edition["title"])+'</title><style>body{font-family:system-ui;margin:0;background:#faf7f2;color:#26313a}'
          'header{padding:4rem 6vw;text-align:center}.grid{display:grid;gap:24px;padding:0 6vw 6vw}'
          '.product{background:white;border-radius:18px;padding:20px;display:grid;grid-template-columns:minmax(180px,34%) 1fr;gap:24px}'
          '.product img{width:100%;max-height:420px;object-fit:contain}.product:target{outline:3px solid #2f6b7a}'
          '@media(max-width:700px){.product{grid-template-columns:1fr}}</style></head><body><header><h1>'+
          _e(edition["title"])+'</h1><p>'+_e(edition.get("subtitle") or "")+'</p></header><main class="grid">'+
          "".join(cards)+'</main></body></html>')
        data=html.encode("utf-8");digest=sha256(data).hexdigest()
        out=self.output_root/str(edition_id)/"digital";out.mkdir(parents=True,exist_ok=True)
        path=out/"index.html";path.write_bytes(data)
        manifest={"schema":"opencrochet.digital.v1","edition_id":edition_id,"sha256":digest,
                  "features":["responsive","lazy_loading","deep_links","accessibility_fallback"]}
        (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,separators=(",",":")),encoding="utf-8")
        asset=self.store.create_asset(edition_id,"EXPORT",None,str(path),digest,actor,{"format":"DIGITAL_HTML","manifest":manifest})
        return asset
