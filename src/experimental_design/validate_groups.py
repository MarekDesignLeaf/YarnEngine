from dataclasses import dataclass
from math import sqrt
from src.calibration.linear import fit_linear_model
from src.calibration.predict import predict_sample
from src.calibration_capture.adapter import to_calibration_sample
from .group_split import leave_one_group_out

@dataclass(frozen=True)
class GroupValidationReport:
    group_field:str
    n_folds:int
    n_predictions:int
    mae_m:float
    rmse_m:float
    mape_percent:float|None
    failed_folds:tuple[str,...]

def validate_by_group(records,group_field,ridge_lambda=1e-4):
    folds=leave_one_group_out(records,group_field)
    errors=[]; apes=[]; failed=[]
    for fold in folds:
        train=[to_calibration_sample(records[i]) for i in fold["train_indices"]]
        test=[to_calibration_sample(records[i]) for i in fold["test_indices"]]
        try:
            model,spec=fit_linear_model(train,ridge_lambda)
            for s in test:
                if any(op not in spec.operation_ids and n>0 for op,n in s.operation_counts.items()):
                    raise ValueError("test fold has unseen operation")
                pred=predict_sample(s,model,spec).estimate_m
                err=pred-s.yarn_length_m
                errors.append(err)
                apes.append(abs(err)/s.yarn_length_m*100)
        except Exception as e:
            failed.append(f"{fold['group']}: {e}")
    if not errors:
        raise ValueError("no valid grouped predictions")
    mae=sum(abs(e) for e in errors)/len(errors)
    rmse=sqrt(sum(e*e for e in errors)/len(errors))
    return GroupValidationReport(group_field,len(folds),len(errors),mae,rmse,sum(apes)/len(apes) if apes else None,tuple(failed))
