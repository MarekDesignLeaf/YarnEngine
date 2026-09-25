"""Deterministic raster-first PDF/X-4 export adapter.

The catalogue compositor currently emits governed page content rather than a
full print renderer. This adapter therefore rasterises the governed content at
300 ppi, embeds no PDF fonts, adds A4 trim and bleed boxes, an sRGB output
intent, XMP PDF/X-4 identification and deterministic object ordering.

It is designed to be fail-closed and mechanically preflightable. External
printer RIP/preflight remains the final authority before commercial printing.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from PIL import Image, ImageCms, ImageDraw, ImageFont
import math
import zlib

MM_TO_PT=72.0/25.4

@dataclass(frozen=True)
class Pdfx4Profile:
    trim_width_mm: float=210.0
    trim_height_mm: float=297.0
    bleed_mm: float=3.0
    target_ppi: int=300
    output_condition_identifier: str="sRGB IEC61966-2.1"

    @property
    def media_width_mm(self): return self.trim_width_mm+2*self.bleed_mm
    @property
    def media_height_mm(self): return self.trim_height_mm+2*self.bleed_mm
    @property
    def media_width_px(self): return round(self.media_width_mm/25.4*self.target_ppi)
    @property
    def media_height_px(self): return round(self.media_height_mm/25.4*self.target_ppi)

def _esc(s:str)->str:
    return str(s).replace("\\","\\\\").replace("(","\\(").replace(")","\\)")

def _xmp(title:str,release_timestamp:str)->bytes:
    xml=f'''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:xmp="http://ns.adobe.com/xap/1.0/"
   xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/">
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">{title}</rdf:li></rdf:Alt></dc:title>
   <xmp:CreateDate>{release_timestamp}</xmp:CreateDate>
   <xmp:ModifyDate>{release_timestamp}</xmp:ModifyDate>
   <pdfxid:GTS_PDFXVersion>PDF/X-4</pdfxid:GTS_PDFXVersion>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''
    return xml.encode("utf-8")

def _render_page(lines:list[str],profile:Pdfx4Profile)->bytes:
    img=Image.new("RGB",(profile.media_width_px,profile.media_height_px),"white")
    draw=ImageDraw.Draw(img)
    try: font=ImageFont.load_default(size=34)
    except TypeError: font=ImageFont.load_default()
    x=round(profile.bleed_mm/25.4*profile.target_ppi)+100
    y=round(profile.bleed_mm/25.4*profile.target_ppi)+120
    line_gap=52
    for line in lines:
        draw.text((x,y),str(line)[:180],fill="black",font=font)
        y+=line_gap
    return img.tobytes()

def build_pdfx4(lines_per_page:list[list[str]],title:str,release_timestamp:str,
                profile:Pdfx4Profile|None=None)->bytes:
    p=profile or Pdfx4Profile()
    icc=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    xmp=_xmp(_esc(title),release_timestamp)

    objects:list[bytes]=[]
    def add(body:bytes|str)->int:
        if isinstance(body,str): body=body.encode("latin-1")
        objects.append(body); return len(objects)

    metadata_id=add(b"<< /Type /Metadata /Subtype /XML /Length "+str(len(xmp)).encode()+b" >>\nstream\n"+xmp+b"\nendstream")
    icc_id=add(b"<< /N 3 /Alternate /DeviceRGB /Length "+str(len(icc)).encode()+b" >>\nstream\n"+icc+b"\nendstream")
    oi_id=add(f"<< /Type /OutputIntent /S /GTS_PDFX /OutputConditionIdentifier ({_esc(p.output_condition_identifier)}) "
              f"/Info ({_esc(p.output_condition_identifier)}) /DestOutputProfile {icc_id} 0 R >>")
    pages_id=add("PLACEHOLDER")

    media_w=p.media_width_mm*MM_TO_PT
    media_h=p.media_height_mm*MM_TO_PT
    bleed=p.bleed_mm*MM_TO_PT
    trim_w=p.trim_width_mm*MM_TO_PT
    trim_h=p.trim_height_mm*MM_TO_PT
    page_ids=[]
    for lines in lines_per_page:
        raw=_render_page(lines,p)
        comp=zlib.compress(raw,9)
        img_id=add(
          f"<< /Type /XObject /Subtype /Image /Width {p.media_width_px} /Height {p.media_height_px} "
          f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(comp)} >>\nstream\n".encode()
          +comp+b"\nendstream")
        content=f"q {media_w:.5f} 0 0 {media_h:.5f} 0 0 cm /Im0 Do Q".encode()
        stream_id=add(b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"\nendstream")
        page_id=add(
          f"<< /Type /Page /Parent {pages_id} 0 R "
          f"/MediaBox [0 0 {media_w:.5f} {media_h:.5f}] "
          f"/BleedBox [0 0 {media_w:.5f} {media_h:.5f}] "
          f"/TrimBox [{bleed:.5f} {bleed:.5f} {bleed+trim_w:.5f} {bleed+trim_h:.5f}] "
          f"/Resources << /XObject << /Im0 {img_id} 0 R >> >> /Contents {stream_id} 0 R >>")
        page_ids.append(page_id)

    objects[pages_id-1]=f"<< /Type /Pages /Count {len(page_ids)} /Kids [{' '.join(f'{x} 0 R' for x in page_ids)}] >>".encode()
    catalog=add(f"<< /Type /Catalog /Pages {pages_id} 0 R /Metadata {metadata_id} 0 R /OutputIntents [{oi_id} 0 R] >>")
    info=add(f"<< /Title ({_esc(title)}) /Producer (OpenCrochet Pro pdfx4-raster-v1) "
             f"/GTS_PDFXVersion (PDF/X-4) >>")

    out=bytearray(b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n")
    offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode());out.extend(obj);out.extend(b"\nendobj\n")
    xref=len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n".encode());out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend((f"trailer\n<< /Size {len(objects)+1} /Root {catalog} 0 R /Info {info} 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n").encode())
    return bytes(out)

def structural_preflight(pdf:bytes,expected_pages:int)->dict:
    required=[
      b"%PDF-1.6",b"/GTS_PDFXVersion (PDF/X-4)",b"/OutputIntents",
      b"/GTS_PDFX",b"/DestOutputProfile",b"/TrimBox",b"/BleedBox",b"/Metadata"
    ]
    missing=[x.decode("latin-1") for x in required if x not in pdf]
    page_count=pdf.count(b"/Type /Page ")
    return {
      "decision":"PASS" if not missing and page_count==expected_pages else "FAIL",
      "missing_tokens":missing,"page_count":page_count,"expected_pages":expected_pages,
      "sha256":sha256(pdf).hexdigest()
    }
