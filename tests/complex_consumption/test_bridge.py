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

def test_no_production_model_falls_back_to_uncalibrated_baseline_instead_of_raising():
 c,p,a=calculate_operation_program(record=None,operation_counts={"SC":50},gauge=Gauge(20,20,100,100),yarn_diameter_mm=2)
 assert c.core_length_m>0 and p.estimate_m>0
 assert c.model_status=="uncalibrated_geometry_baseline"
 assert a["estimate_basis"]=="uncalibrated_geometry_baseline"
 assert p.in_domain is False

def test_uncalibrated_baseline_reports_unsupported_operations():
 c,p,a=calculate_operation_program(record=None,operation_counts={"SC":10,"NOT_A_STITCH":5},gauge=Gauge(20,20,100,100),yarn_diameter_mm=2)
 assert a["unsupported_operations"]==["NOT_A_STITCH"]

def test_calibrated_record_is_still_preferred_over_baseline_when_available():
 c,p,a=calculate_operation_program(record=REC,operation_counts={"SC":1000},gauge=Gauge(20,20,100,100),yarn_diameter_mm=2)
 assert a["estimate_basis"]=="calibrated_production_model"
 assert round(p.estimate_m,6)==100
