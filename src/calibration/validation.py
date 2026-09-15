from dataclasses import dataclass
from math import sqrt
from .linear import fit_linear_model
from .predict import predict_sample

@dataclass(frozen=True)
class CrossValidationReport:
    n_samples:int
    mae_m:float
    rmse_m:float
    mean_absolute_percent_error:float | None
    errors:tuple[float,...]

def leave_one_out(samples, ridge_lambda=1e-6):
    samples=list(samples)
    if len(samples)<4:
        raise ValueError("at least 4 samples required for leave-one-out validation")
    errors=[]; ape=[]
    for i,test in enumerate(samples):
        train=samples[:i]+samples[i+1:]
        model,spec=fit_linear_model(train,ridge_lambda)
        # If test contains an unseen op, feature spec cannot represent it -> validation is invalid.
        if any(op not in spec.operation_ids and n>0 for op,n in test.operation_counts.items()):
            raise ValueError("leave-one-out fold contains an operation absent from training data")
        pred=predict_sample(test,model,spec).estimate_m
        err=pred-test.yarn_length_m
        errors.append(err)
        if test.yarn_length_m>0:
            ape.append(abs(err)/test.yarn_length_m*100)
    mae=sum(abs(e) for e in errors)/len(errors)
    rmse=sqrt(sum(e*e for e in errors)/len(errors))
    mape=sum(ape)/len(ape) if ape else None
    return CrossValidationReport(len(samples),mae,rmse,mape,tuple(errors))
