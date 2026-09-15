from dataclasses import dataclass,asdict
from collections import Counter,defaultdict
from src.pattern_engine.loader import load_pattern_dict

@dataclass(frozen=True)
class LabRecord:
    swatch_id:int
    name:str
    pattern_id:str
    pattern_version:str
    yarn_id:str
    needle_mm:float|None
    stitches:int
    rows:int
    width_cm:float
    height_cm:float
    yarn_length_m:float|None
    yarn_mass_g:float|None
    yarn_diameter_mm:float|None
    tex:float|None
    operation_counts:dict[str,int]
    wale_spacing_mm:float
    course_spacing_mm:float

def repeat_operation_counts(pattern):
    out=Counter()
    for row in pattern.rows:
        for token in row.sequence:
            out[token.op]+=token.n
    return dict(out)

def derive_operation_counts(pattern,stitches,rows):
    if stitches % pattern.repeat_width_stitches or rows % pattern.repeat_height_rows:
        raise ValueError("swatch grid must contain whole pattern repeats for calibration operation accounting")
    factor=(stitches//pattern.repeat_width_stitches)*(rows//pattern.repeat_height_rows)
    return {k:v*factor for k,v in repeat_operation_counts(pattern).items()}

def build_lab_record(swatch,yarn,pattern):
    ops=derive_operation_counts(pattern,int(swatch["stitches"]),int(swatch["rows"]))
    return LabRecord(
      int(swatch["swatch_id"]),swatch["name"],swatch["pattern_id"],swatch["pattern_version"],swatch["yarn_id"],
      swatch.get("needle_mm"),int(swatch["stitches"]),int(swatch["rows"]),float(swatch["width_cm"]),float(swatch["height_cm"]),
      swatch.get("yarn_length_m"),swatch.get("yarn_mass_g"),yarn.get("nominal_diameter_mm"),
      yarn.get("tex") or (float(yarn["package_mass_g"])/float(yarn["package_length_m"])*1000.0),
      ops,float(swatch["width_cm"])*10/int(swatch["stitches"]),float(swatch["height_cm"])*10/int(swatch["rows"])
    )

def coverage(records):
    op_records=Counter()
    patterns=Counter();yarns=Counter()
    for r in records:
        patterns[r.pattern_id]+=1;yarns[r.yarn_id]+=1
        for op,n in r.operation_counts.items():
            if n>0:op_records[op]+=1
    return {"records":len(records),"patterns":dict(patterns),"yarns":dict(yarns),"operation_record_counts":dict(op_records)}

def readiness(records,min_records=6,min_distinct_patterns=2,min_distinct_yarns=2):
    c=coverage(records);reasons=[]
    if c["records"]<min_records:reasons.append(f"need at least {min_records} eligible swatches")
    if len(c["patterns"])<min_distinct_patterns:reasons.append(f"need at least {min_distinct_patterns} distinct patterns")
    if len(c["yarns"])<min_distinct_yarns:reasons.append(f"need at least {min_distinct_yarns} distinct yarns")
    if any(r.yarn_length_m is None for r in records):reasons.append("all calibration records require measured yarn length")
    return {"ready":not reasons,"reasons":reasons,"coverage":c,
            "note":"Thresholds are project protocol gates, not published universal calibration standards."}
