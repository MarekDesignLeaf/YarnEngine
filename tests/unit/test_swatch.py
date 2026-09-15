from src.calibration.swatch import CoreSwatchCalibration

def test_stitch_position_scaling():
    c=CoreSwatchCalibration(40,50,20.0)
    assert c.stitch_positions==2000
    assert abs(c.metres_per_stitch_position-0.01)<1e-12
    assert abs(c.predict_core_length_m(200,300)-600.0)<1e-12
