from src.calibration.uncertainty import empirical_absolute_error_interval,validation_summary
def test_empirical_interval():
 x=empirical_absolute_error_interval(100,[1,-2,3,-4]*6)
 assert x.n_validation_errors==24 and x.calibrated and x.lower_m<100<x.upper_m
def test_small_sample_is_flagged():
 x=empirical_absolute_error_interval(10,[1,2,3])
 assert not x.calibrated and x.warning
def test_no_errors_makes_no_claim():
 x=empirical_absolute_error_interval(10,[])
 assert not x.calibrated and x.method=="none"
def test_summary():
 x=validation_summary([1,-1,2,-2]);assert x["n"]==4 and x["mae_m"]==1.5 and x["bias_m"]==0
