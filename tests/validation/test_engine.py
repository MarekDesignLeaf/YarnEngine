from src.gauge_engine.gauge import Gauge
from src.calibration.swatch import CoreSwatchCalibration
from src.consumption.engine import calculate_from_swatch, calculate_plain_geometry

def test_tier_a_end_to_end():
    g=Gauge(18,24,100,100)
    c=CoreSwatchCalibration(36,48,12.0)
    r=calculate_from_swatch(width_mm=1200,height_mm=1800,gauge=g,calibration=c,
                            allowance_percent=8,tex=250,package_length_m=200)
    # 216*432 stitch positions, each 12/(36*48) m
    expected=(216*432)*(12/(36*48))
    assert abs(r.core_length_m-expected)<1e-9
    assert abs(r.recommended_length_m-expected*1.08)<1e-9
    assert r.packages >= 1
    assert r.tier=="A"

def test_tier_b_has_warning():
    g=Gauge(18,24,100,100)
    r=calculate_plain_geometry(width_mm=100,height_mm=100,gauge=g,yarn_diameter_mm=1.0)
    assert r.tier=="B"
    assert "unvalidated" in r.model_status
    assert len(r.warnings)>=1
