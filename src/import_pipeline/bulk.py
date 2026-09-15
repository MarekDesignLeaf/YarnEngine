import json
from pathlib import Path
from .core import import_yarn_file,import_pattern_bundle

def bulk_import_yarns(store,folder):
    results=[]
    for f in sorted(Path(folder).glob("*.json")):
        if f.name.endswith("_TEMPLATE.json"): continue
        results.append(import_yarn_file(store,f))
    return tuple(results)

def bulk_import_patterns(store,pattern_folder,metadata_file,operations):
    meta_raw=json.loads(Path(metadata_file).read_text())
    meta={(m["pattern_id"],m["version"]):m for m in meta_raw["patterns"]}
    results=[]
    for f in sorted(Path(pattern_folder).glob("*.json")):
        d=json.loads(f.read_text())
        key=(d.get("pattern_id"),d.get("version"))
        if key not in meta:
            store.quarantine("pattern",str(f),f.read_text(),"MISSING_METADATA","no matching metadata",__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat())
            results.append({"status":"quarantined","entity":"pattern","source":str(f),"error":"no matching metadata"})
        else:
            results.append(import_pattern_bundle(store,f,meta[key],operations))
    return tuple(results)
