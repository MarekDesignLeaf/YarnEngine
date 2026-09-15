import json,hashlib,datetime
from pathlib import Path
from src.library.yarn import YarnRecord
from src.library.pattern_meta import PatternMetadata
from src.pattern_engine.loader import load_pattern_dict
from src.pattern_engine.registry import load_operation_registry
from src.pattern_engine.validation import validate_pattern

def canonical_checksum(obj):
    raw=json.dumps(obj,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def validate_yarn_dict(d):
    clean={k:v for k,v in d.items() if k!="record_type"}
    YarnRecord(**clean)
    return clean

def validate_pattern_bundle(pattern,meta,operations):
    p=load_pattern_dict(pattern)
    m=PatternMetadata(**{**meta,"tags":tuple(meta.get("tags",[])),"techniques":tuple(meta.get("techniques",[]))})
    if p.pattern_id!=m.pattern_id or p.version!=m.version:
        raise ValueError("pattern/metadata identity mismatch")
    rep=validate_pattern(p,operations)
    if not rep.valid:
        raise ValueError("; ".join(f"{i.code}:{i.message}" for i in rep.issues))
    return p,m

def import_yarn_file(store,path):
    path=Path(path); now=utc_now()
    try:
        d=json.loads(path.read_text())
        if d.get("record_type")!="yarn":
            raise ValueError("record_type must be yarn")
        clean=validate_yarn_dict(d)
        checksum=canonical_checksum(d)
        store.upsert_yarn(clean,checksum,now)
        store.audit(entity_type="yarn",entity_id=clean["yarn_id"],version=None,
                    source_type=clean.get("source_type"),source_reference=clean.get("source_reference"),
                    license_id=None,evidence_level=clean.get("evidence_level"),checksum=checksum,imported_at=now)
        return {"status":"imported","entity":"yarn","id":clean["yarn_id"],"checksum":checksum}
    except Exception as e:
        raw=path.read_text(errors="replace") if path.exists() else ""
        store.quarantine("yarn",str(path),raw,"VALIDATION_ERROR",str(e),now)
        return {"status":"quarantined","entity":"yarn","source":str(path),"error":str(e)}

def import_pattern_bundle(store,pattern_path,meta,operations):
    pattern_path=Path(pattern_path); now=utc_now()
    try:
        d=json.loads(pattern_path.read_text())
        p,m=validate_pattern_bundle(d,meta,operations)
        checksum=canonical_checksum({"pattern":d,"metadata":meta})
        store.upsert_pattern(d,meta,checksum,now)
        store.audit(entity_type="pattern",entity_id=p.pattern_id,version=p.version,
                    source_type=m.source_type,source_reference=m.source_reference,
                    license_id=m.license_id,evidence_level=None,checksum=checksum,imported_at=now)
        return {"status":"imported","entity":"pattern","id":p.pattern_id,"version":p.version,"checksum":checksum}
    except Exception as e:
        raw=pattern_path.read_text(errors="replace") if pattern_path.exists() else ""
        store.quarantine("pattern",str(pattern_path),raw,"VALIDATION_ERROR",str(e),now)
        return {"status":"quarantined","entity":"pattern","source":str(pattern_path),"error":str(e)}
