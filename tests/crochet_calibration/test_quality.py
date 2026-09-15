from src.crochet_calibration.record import CrochetCalibrationRecord
from src.crochet_calibration.quality import replicate_quality,measurement_consistency
def r(i,length,mass=None,tex=None):
 return CrochetCalibrationRecord(str(i),"g","c","y",3,20,20,100,100,{"SC":400},length,yarn_mass_g=mass,tex=tex,yarn_diameter_mm=2,construction="spiral")
def test_tight_replicates_pass():
 q=replicate_quality([r(1,10),r(2,10.1),r(3,9.9)])
 assert q["overall"]=="pass"
def test_scattered_replicates_fail():
 q=replicate_quality([r(1,5),r(2,10),r(3,15)])
 assert q["overall"]=="fail"
def test_mass_tex_consistency_detects_mismatch():
 q=measurement_consistency([r(1,10,mass=10,tex=500)])
 assert not q["valid"] and q["issues"][0]["code"]=="MASS_LENGTH_MISMATCH"
