"""Reproducible print export.

The exporter writes a deterministic, valid PDF using only standard PDF objects.
It intentionally keeps the rendering profile explicit and records every source
page hash. A production PDF/X renderer can replace this adapter without changing
the export contract.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import json


def _pdf_escape(s:str)->str:
    return str(s).replace("\\","\\\\").replace("(","\\(").replace(")","\\)")


def _minimal_pdf(lines_per_page:list[list[str]], title:str)->bytes:
    objects=[]
    def add(body:str)->int:
        objects.append(body);return len(objects)
    font=add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    pages_id=add("PLACEHOLDER")
    page_ids=[]
    for lines in lines_per_page:
        stream="BT /F1 12 Tf 54 790 Td 16 TL "
        first=True
        for line in lines:
            if not first: stream+="T* "
            first=False
            stream+="("+_pdf_escape(line[:150])+") Tj "
        stream+="ET"
        stream_id=add("<< /Length %d >>\nstream\n%s\nendstream"%(len(stream.encode("latin-1","replace")),stream))
        page_id=add("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"%(pages_id,font,stream_id))
        page_ids.append(page_id)
    objects[pages_id-1]="<< /Type /Pages /Count %d /Kids [%s] >>"%(len(page_ids)," ".join(f"{x} 0 R" for x in page_ids))
    catalog=add("<< /Type /Catalog /Pages %d 0 R >>"%pages_id)
    info=add("<< /Title (%s) /Producer (OpenCrochet Pro deterministic-pdf-v1) >>"%_pdf_escape(title))
    out=bytearray(b"%PDF-1.4\n")
    offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode());out.extend(obj.encode("latin-1","replace"));out.extend(b"\nendobj\n")
    xref=len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode());out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(("trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"%
                (len(objects)+1,catalog,info,xref)).encode())
    return bytes(out)


class PrintExporter:
    DEFAULT_PROFILE={"profile_id":"A4_PRINT_V1","page_size":"A4","bleed_mm":3,
                     "target_ppi":300,"reproducibility":"BYTE_IDENTICAL",
                     "pdf_profile":"PDF-1.4","renderer_version":"minimal-pdf-v1",
                     "font_bundle_hash":"builtin-helvetica",
                     "object_order_policy":"stable-source-order-v1"}

    def __init__(self, store, output_root:Path):
        self.store=store;self.output_root=Path(output_root)

    def export(self, edition_id:int, actor:str|None, profile:dict|None=None):
        edition=self.store.get(edition_id)
        if not edition:raise KeyError("catalogue edition not found")
        if edition["state"] not in {"COVER_VALIDATING","FINAL_VALIDATING","RELEASE_APPROVED","EXPORTED"}:
            raise ValueError("print export requires validated cover/final stage")
        p=dict(self.DEFAULT_PROFILE);p.update(profile or {})
        p.setdefault("release_timestamp",edition.get("released_at") or edition.get("created_at"))
        from .governance import validate_reproducibility_profile
        validate_reproducibility_profile(p)
        assets=self.store.list_assets(edition_id)
        pages=sorted([a for a in assets if a["asset_type"]=="PAGE" and a["state"] not in {"STALE","SUPERSEDED"}],
                     key=lambda a:int(a["metadata"].get("page_number") or 0))
        covers=[a for a in assets if a["asset_type"]=="COVER" and a["state"] not in {"STALE","SUPERSEDED"}]
        if not pages:raise ValueError("no current catalogue pages")
        if not covers:raise ValueError("no current cover")
        lines=[["COVER",edition["title"],edition.get("subtitle") or "",
                "Cover SHA256: "+str(covers[-1].get("sha256") or "")]]
        for a in pages:
            m=a["metadata"].get("composition_manifest") or {}
            lines.append([
              "Page "+str(m.get("page_number") or a["metadata"].get("page_number") or ""),
              str(m.get("display_name") or ""),
              "Product ID: "+str(m.get("product_id") or ""),
              str(m.get("description") or ""),
              "Page source SHA256: "+str(a.get("sha256") or "")
            ])
        pdf=_minimal_pdf(lines,edition["title"])
        digest=sha256(pdf).hexdigest()
        out=self.output_root/str(edition_id);out.mkdir(parents=True,exist_ok=True)
        path=out/"catalogue.pdf";path.write_bytes(pdf)
        manifest={"schema":"opencrochet.print.export.v1","edition_id":edition_id,
                  "profile":p,"cover_sha256":covers[-1].get("sha256"),
                  "page_sha256":[a.get("sha256") for a in pages],"export_sha256":digest}
        (out/"print_export_manifest.json").write_text(json.dumps(manifest,sort_keys=True,separators=(",",":")),encoding="utf-8")
        asset=self.store.create_asset(edition_id,"EXPORT",None,str(path),digest,actor,{
          "format":"PDF","profile":p,"export_manifest":manifest
        })
        for a in [covers[-1],*pages]:
            self.store.add_dependency(edition_id,"ASSET",a["id"],str(a["version"]),"ASSET",asset["id"])
        return asset
