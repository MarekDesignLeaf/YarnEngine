"""Interior catalogue builder."""
from __future__ import annotations
from pathlib import Path
from .composer import compose_product_page, compose_interior_manifest

class InteriorBuilder:
    def __init__(self, store, output_root:Path):
        self.store=store
        self.output_root=Path(output_root)

    def build(self, edition_id:int, brand:dict, actor:str|None):
        edition=self.store.get(edition_id)
        if not edition:raise KeyError("catalogue edition not found")
        manifest=edition["manifest"]
        products=manifest.get("products") or []
        if not products:raise ValueError("catalogue has no products")
        output=self.output_root/str(edition_id)
        output.mkdir(parents=True,exist_ok=True)
        pages=[]
        for page_number,p in enumerate(products,1):
            pid=int(p["product_line_id"])
            masters=[m for m in self.store.list_product_masters(pid) if m["state"]=="APPROVED"]
            if not masters:raise ValueError(f"product {pid} has no approved Product Master Record")
            pm=masters[0]
            visuals=[a for a in self.store.list_assets(edition_id)
                     if a["product_line_id"]==pid and a["asset_type"]=="MASTER_VISUAL" and a["state"]=="LOCKED"
                     and str(a.get("source_record_version"))==str(pm["version"])]
            if not visuals:raise ValueError(f"product {pid} has no locked current Master Visual")
            visual=max(visuals,key=lambda a:a["version"])
            product=dict(pm["record"])
            if not product.get("description"):product["description"]=p.get("description") or ""
            page=compose_product_page(page_number=page_number,product=product,master_visual=visual,
                                      brand=brand,locale=manifest.get("locale","en-GB"))
            path=output/f"page_{page_number:04d}.html"
            path.write_bytes(page.html)
            asset=self.store.create_asset(edition_id,"PAGE",pid,str(path),page.sha256,actor,
              {"page_number":page_number,"composer":"deterministic-html-v1",
               "source_master_visual_id":visual["id"],"composition_manifest":page.manifest},
              str(pm["version"]))
            self.store.add_dependency(edition_id,"ASSET",visual["id"],str(visual["version"]),"ASSET",asset["id"])
            pages.append({"page_number":page_number,"asset_id":asset["id"],"sha256":page.sha256})
        raw,digest=compose_interior_manifest(edition_id,pages)
        mpath=output/"interior_manifest.json";mpath.write_bytes(raw)
        return {"edition_id":edition_id,"pages":pages,"manifest_uri":str(mpath),"manifest_sha256":digest}
