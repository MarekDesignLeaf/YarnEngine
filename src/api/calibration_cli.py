import argparse,json
from pathlib import Path
from src.calibration.dataset import CalibrationSample
from src.calibration.linear import fit_linear_model
from src.calibration.validation import leave_one_out
from src.calibration.serialization import save_model

def main():
    p=argparse.ArgumentParser()
    p.add_argument("dataset")
    p.add_argument("--out-model",required=True)
    p.add_argument("--ridge",type=float,default=1e-6)
    a=p.parse_args()
    raw=json.loads(Path(a.dataset).read_text())
    data=raw["samples"] if isinstance(raw,dict) and "samples" in raw else raw
    samples=[CalibrationSample(**x) for x in data]
    model,spec=fit_linear_model(samples,a.ridge)
    save_model(a.out_model,model,spec)
    report={"fit":{"n_samples":model.n_samples,"rmse_m":model.rmse_m,"mae_m":model.mae_m,"mean_error_m":model.mean_error_m}}
    if len(samples)>=4:
        try:
            cv=leave_one_out(samples,a.ridge)
            report["leave_one_out"]=cv.__dict__
        except ValueError as e:
            report["leave_one_out_warning"]=str(e)
    print(json.dumps(report,indent=2))
if __name__=="__main__": main()
