import pytest
from src.complex_consumption.bridge import calculate_operation_program
from src.gauge_engine.gauge import Gauge

REC={"model":{"feature_names":["intercept","op:SC/1000","wale_spacing_mm","course_spacing_mm","yarn_diameter_mm"],
"coefficients":[0,100,0,0,0],"operation_ids":["SC"],"rmse_m":.1,"mae_m":.1,"mean_error_m":0,
"residual_std_m":.1,"n_samples":30,"ridge_lambda":1e-6,
"domains":{"operation_ids":["SC"],"wale_spacing_mm":[4,6],"course_spacing_mm":[4,6],"yarn_diameter_mm":[1,3]}},
"validation":{"errors":[.1,-.1,.2,-.2]*6}}
def test_operation_counts_are_authoritative():
 c,p,a=calculate_operation_program(record=REC,operation_counts={"SC":1000},gauge=Gauge(20,20,100,100),
 yarn_diameter_mm=2,domain_policy="strict")
 assert round(p.estimate_m,6)==100 and a["rectangular_area_used_for_operation_counts"] is False
def test_empty_program_rejected():
 with pytest.raises(ValueError):
  calculate_operation_program(record=REC,operation_counts={},gauge=Gauge(20,20,100,100),yarn_diameter_mm=2)
