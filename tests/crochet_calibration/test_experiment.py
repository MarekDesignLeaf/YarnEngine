from src.crochet_calibration.experiment import generate_experiment_plan
from src.crochet_calibration.record import CrochetCalibrationRecord
def rec(i,op="SC"):
 return CrochetCalibrationRecord(str(i),"EXP_SC_SPIRAL","c","y",3,20,20,100,100,{op:400},10,yarn_diameter_mm=2,construction="spiral")
def test_empty_plan_requests_core_evidence():
 p=generate_experiment_plan([],required_ops=("SC","SC_INC"),min_records_per_op=3,min_replicates=3)
 assert p["count"]==6 and not p["complete"]
def test_existing_records_reduce_work():
 p=generate_experiment_plan([rec(1),rec(2),rec(3)],required_ops=("SC",),min_records_per_op=3,min_replicates=3)
 assert p["complete"] and p["count"]==0
def test_plan_has_no_fake_measurement():
 p=generate_experiment_plan([],required_ops=("SC",),min_records_per_op=1,min_replicates=1)
 assert p["experiments"][0]["instruction"]["operation_count_target"] is None
