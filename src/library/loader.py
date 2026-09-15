import json
from pathlib import Path
from .yarn import YarnRecord
from .pattern_meta import PatternMetadata
from .registry import LibraryRegistry
from src.pattern_engine.loader import load_pattern_file

def load_library(root):
    root=Path(root); reg=LibraryRegistry.empty()
    for f in sorted((root/"data/yarns").glob("*.json")):
        d=json.loads(f.read_text())
        if d.get("record_type")=="yarn" and not f.name.endswith("_TEMPLATE.json"):
            reg.add_yarn(YarnRecord(**{k:v for k,v in d.items() if k!="record_type"}))
    meta={}
    mf=root/"data/library/pattern_metadata.json"
    if mf.exists():
        for d in json.loads(mf.read_text())["patterns"]:
            m=PatternMetadata(**{**d,"tags":tuple(d.get("tags",[])),"techniques":tuple(d.get("techniques",[]))})
            meta[(m.pattern_id,m.version)]=m
    for f in sorted((root/"data/patterns").glob("*.json")):
        p=load_pattern_file(f); key=(p.pattern_id,p.version)
        if key in meta: reg.add_pattern(p,meta[key])
    return reg
