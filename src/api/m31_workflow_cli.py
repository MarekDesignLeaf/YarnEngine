import argparse,json
from pathlib import Path
from dataclasses import asdict
from src.calibration_capture.record import RealSwatchRecord,MeasurementEvidence
from src.calibration_capture.replicates import summarize_replicates,flag_unstable_replicates
from src.experimental_design.coverage import analyse_coverage
def main():
    p=argparse.ArgumentParser()
    p.add_argument("records")
    a=p.parse_args()
    raw=json.loads(Path(a.records).read_text())
    rows=raw["records"] if isinstance(raw,dict) else raw
    rec=[RealSwatchRecord(**{**x,"evidence":MeasurementEvidence(**x["evidence"])}) for x in rows]
    out={
      "replicates":[asdict(x) for x in summarize_replicates(rec)],
      "replicate_flags":list(flag_unstable_replicates(rec)),
      "coverage":asdict(analyse_coverage(rec))
    }
    print(json.dumps(out,indent=2))
if __name__=="__main__": main()
