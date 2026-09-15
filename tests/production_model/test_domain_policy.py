import pytest
from src.production_model.runtime import calculate_with_production_model
from src.gauge_engine.gauge import Gauge

REC={"model":{"feature_names":["intercept","op:K","wale_spacing_mm","course_spacing_mm","yarn_diameter_mm"],
"coefficients":[0,0.01,0,0,0],"operation_ids":["K"],"rmse_m":0.1,"mae_m":0.1,"mean_error_m":0,
"residual_std_m":0.1,"n_samples":10,"ridge_lambda":1e-6,
"domains":{"operation_ids":["K"],"wale_spacing_mm":[1,2],"course_spacing_mm":[1,2],"yarn_diameter_mm":[1,2]}}}
def test_strict_rejects_out_of_domain():
 with pytest.raises(ValueError,match="outside the calibrated domain"):
  calculate_with_production_model(record=REC,operation_counts={"K":10},gauge=Gauge(20,20,100,100),
   width_mm=100,height_mm=100,yarn_diameter_mm=1.5,allowance_percent=0,domain_policy="strict")
def test_warn_allows_out_of_domain():
 calc,p=calculate_with_production_model(record=REC,operation_counts={"K":10},gauge=Gauge(20,20,100,100),
   width_mm=100,height_mm=100,yarn_diameter_mm=1.5,allowance_percent=0,domain_policy="warn")
 assert not p.in_domain and calc.tier=="B"
