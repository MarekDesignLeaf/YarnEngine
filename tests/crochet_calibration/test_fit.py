from src.crochet_calibration.record import CrochetCalibrationRecord
from src.crochet_calibration.fit import fit_crochet_model
def test_crochet_fit_is_scoped():
 rs=[]
 for i in range(6):
  rs.append(CrochetCalibrationRecord(str(i),f"g{i//3}","c","y",3,20,20,100,100,
   {"SC":400+i*20},10+i*.5,yarn_diameter_mm=2,construction="spiral"))
 r=fit_crochet_model(rs)
 assert r["model_scope"]=="crochet" and "SC" in r["model"]["operation_ids"] and r["model"]["n_samples"]==6
