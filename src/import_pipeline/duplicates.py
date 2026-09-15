import json
from collections import defaultdict
from src.pattern_engine.loader import load_pattern_dict
from src.pattern_engine.analyse import pattern_signature

def duplicate_pattern_groups(pattern_dicts):
    buckets=defaultdict(list)
    for d in pattern_dicts:
        p=load_pattern_dict(d)
        sig=pattern_signature(p)
        key=json.dumps(sig,sort_keys=True,separators=(",",":"))
        buckets[key].append((p.pattern_id,p.version))
    return tuple(tuple(v) for v in buckets.values() if len(v)>1)

def near_duplicate_yarns(yarns):
    """Simple deterministic candidate detector, not an identity claim."""
    groups=defaultdict(list)
    for y in yarns:
        key=(
          (y.get("brand") or "").strip().lower(),
          (y.get("product") or "").strip().lower(),
          round(float(y.get("package_mass_g",0)),3),
          round(float(y.get("package_length_m",0)),3)
        )
        groups[key].append(y["yarn_id"])
    return tuple(tuple(v) for v in groups.values() if len(v)>1)
