import argparse, json
from pathlib import Path
from src.pattern_engine.loader import load_pattern_file
from src.pattern_engine.registry import load_operation_registry
from src.pattern_engine.validation import validate_pattern
from src.pattern_engine.expand import expand_full_repeats
from src.pattern_engine.analyse import pattern_signature

def main():
    p=argparse.ArgumentParser(description="Inspect/validate/expand a knitting pattern")
    p.add_argument("pattern")
    p.add_argument("--operations",default="data/stitches/operations.seed.json")
    p.add_argument("--width-stitches",type=int)
    p.add_argument("--height-rows",type=int)
    a=p.parse_args()

    pattern=load_pattern_file(a.pattern)
    ops=load_operation_registry(a.operations)
    report=validate_pattern(pattern,ops)
    out={
      "pattern_id":pattern.pattern_id,
      "version":pattern.version,
      "valid":report.valid,
      "issues":[i.__dict__ for i in report.issues],
      "signature":pattern_signature(pattern)
    }
    if report.valid and a.width_stitches and a.height_rows:
        out["expanded"]=expand_full_repeats(pattern,a.width_stitches,a.height_rows).__dict__
    print(json.dumps(out,indent=2))

if __name__=="__main__":
    main()
