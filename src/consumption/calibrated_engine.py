from dataclasses import dataclass
from src.calibration.dataset import CalibrationSample
from src.calibration.predict import predict_sample
from src.domain.units import mass_g_from_length_m, packages_required

@dataclass(frozen=True)
class CalibratedConsumptionResult:
    core_length_m:float
    lower_95_m:float
    upper_95_m:float
    recommended_length_m:float
    mass_g:float|None
    packages:int|None
    in_domain:bool
    warnings:tuple[str,...]
    model_samples:int
    model_rmse_m:float

def calculate_calibrated(*,operation_counts,wale_spacing_mm,course_spacing_mm,
                         yarn_diameter_mm,model,spec,allowance_percent=0.0,
                         tex=None,package_length_m=None):
    if allowance_percent<0: raise ValueError("allowance_percent must be >= 0")
    synthetic=CalibrationSample(
       calibration_id="PROJECT_PREDICTION",pattern_id="PROJECT",
       operation_counts=operation_counts,yarn_length_m=1.0,
       wale_spacing_mm=wale_spacing_mm,course_spacing_mm=course_spacing_mm,
       yarn_diameter_mm=yarn_diameter_mm,tex=tex
    )
    p=predict_sample(synthetic,model,spec)
    rec=p.estimate_m*(1+allowance_percent/100.0)
    mass=mass_g_from_length_m(rec,tex) if tex is not None else None
    packs=packages_required(rec,package_length_m) if package_length_m is not None else None
    return CalibratedConsumptionResult(
       p.estimate_m,p.lower_95_m,p.upper_95_m,rec,mass,packs,p.in_domain,p.warnings,
       model.n_samples,model.rmse_m
    )
