import hashlib,json,re,datetime
from dataclasses import dataclass,asdict
from src.pattern_engine.loader import load_pattern_dict
from src.pattern_engine.validation import validate_pattern
from src.library.pattern_meta import PatternMetadata
from src.library_scaling.pipeline import structural_signature

def checksum(obj):
 return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def safe_id(s):
 s=re.sub(r"[^A-Z0-9_]+","_",s.upper().strip()).strip("_")
 if not s:raise ValueError("pattern_id cannot normalize to empty")
 return s
def normalize_bundle(raw):
 """Normalize only explicit structured fields. Does not infer stitch semantics from prose."""
 p=raw.get("pattern",raw)
 meta=raw.get("metadata",{})
 pid=safe_id(p.get("pattern_id") or meta.get("pattern_id") or "")
 version=str(p.get("version") or meta.get("version") or "1.0.0")
 name=str(p.get("name") or meta.get("name") or pid)
 repeat=p.get("repeat") or {}
 rows=[]
 for i,r in enumerate(p.get("rows",[]),1):
  seq=[]
  for tok in r.get("sequence",[]):
   if isinstance(tok,str):seq.append({"op":tok.strip().upper(),"n":1})
   else:seq.append({"op":str(tok["op"]).strip().upper(),"n":int(tok.get("n",1))})
  rows.append({"row":int(r.get("row",i)),"side":str(r.get("side","NA")).upper(),"sequence":seq})
 pattern={"pattern_id":pid,"version":version,"name":name,"technique":"knitting",
  "repeat":{"width_stitches":int(repeat.get("width_stitches",0)),"height_rows":int(repeat.get("height_rows",len(rows)))},
  "rows":rows}
 metadata={"pattern_id":pid,"version":version,"name":name,
  "family_id":str(meta.get("family_id","UNCLASSIFIED")).upper(),
  "tags":sorted(set(str(x).lower() for x in meta.get("tags",[]))),
  "difficulty":str(meta.get("difficulty","unknown")).lower(),
  "techniques":sorted(set(str(x).lower() for x in meta.get("techniques",["knitting"]))),
  "source_type":str(meta.get("source_type","user_import")),
  "source_reference":meta.get("source_reference"),"license_id":meta.get("license_id"),"active":bool(meta.get("active",True))}
 return {"pattern":pattern,"metadata":metadata}

def inspect_bundle(raw,operations,existing_rows=()):
 try:
  b=normalize_bundle(raw);p=load_pattern_dict(b["pattern"])
  m=PatternMetadata(**{**b["metadata"],"tags":tuple(b["metadata"]["tags"]),"techniques":tuple(b["metadata"]["techniques"])})
  v=validate_pattern(p,operations)
  issues=[asdict(x) for x in v.issues]
  if m.source_type not in {"internal","user_created","user_import","licensed","public_domain","synthetic_test"}:
   issues.append({"severity":"warning","code":"SOURCE_TYPE_UNRECOGNIZED","message":"source_type is retained but not independently verified","row":None})
  if not m.source_reference:
   issues.append({"severity":"warning","code":"SOURCE_REFERENCE_MISSING","message":"No source reference supplied","row":None})
  if not m.license_id:
   issues.append({"severity":"warning","code":"LICENSE_UNSPECIFIED","message":"No license identifier supplied; review before redistribution","row":None})
  ch=checksum(b)
  duplicate=None
  for r in existing_rows:
   if r.get("checksum")==ch:duplicate={"type":"exact_checksum","pattern_id":r["pattern_id"],"version":r["version"]}
   elif r["pattern_id"]==p.pattern_id and r["version"]==p.version:duplicate={"type":"identity_conflict","pattern_id":p.pattern_id,"version":p.version}
  return {"valid":v.valid,"bundle":b,"issues":issues,"checksum":ch,"structural_signature":structural_signature(b["pattern"]),"duplicate":duplicate,
   "review_required":any(x["severity"]=="warning" for x in issues) or duplicate is not None}
 except Exception as e:
  return {"valid":False,"bundle":None,"issues":[{"severity":"error","code":"NORMALIZATION_ERROR","message":str(e),"row":None}],
   "checksum":None,"duplicate":None,"review_required":True}

def batch_inspect(items,operations,existing_rows=()):
 reports=[inspect_bundle(x,operations,existing_rows) for x in items]
 return {"total":len(reports),"valid":sum(x["valid"] for x in reports),
  "invalid":sum(not x["valid"] for x in reports),"review_required":sum(x["review_required"] for x in reports),"reports":reports}
