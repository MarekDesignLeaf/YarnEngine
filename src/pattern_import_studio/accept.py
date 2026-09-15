import json,datetime
from pathlib import Path
from src.import_pipeline.core import validate_pattern_bundle,canonical_checksum
def accept_bundle(root,store,bundle,operations,allow_review=False):
 p=bundle["pattern"];m=bundle["metadata"]
 validate_pattern_bundle(p,m,operations)
 if not m.get("source_reference") and not allow_review:
  raise ValueError("source_reference required before accepted library import")
 if not m.get("license_id") and not allow_review:
  raise ValueError("license_id required before accepted library import")
 exists=store.conn.execute("SELECT checksum FROM patterns WHERE pattern_id=? AND version=?",(p["pattern_id"],p["version"])).fetchone()
 if exists:raise ValueError("pattern identity/version already exists")
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();ch=canonical_checksum({"pattern":p,"metadata":m})
 store.upsert_pattern(p,m,ch,now)
 store.audit(entity_type="pattern",entity_id=p["pattern_id"],version=p["version"],source_type=m["source_type"],
  source_reference=m.get("source_reference"),license_id=m.get("license_id"),evidence_level=None,checksum=ch,imported_at=now)
 out=Path(root)/"data/patterns"/f"import_{p['pattern_id'].lower()}_{p['version'].replace('.','_')}.json"
 out.write_text(json.dumps(p,indent=2),encoding="utf-8")
 return {"status":"accepted","pattern_id":p["pattern_id"],"version":p["version"],"checksum":ch,"file":str(out)}
