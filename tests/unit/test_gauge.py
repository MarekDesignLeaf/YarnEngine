from src.gauge_engine.gauge import Gauge, project_grid, RoundingMode

def test_spacing_and_grid():
    g=Gauge(18,24,100,100)
    assert abs(g.wale_spacing_mm - 100/18) < 1e-12
    assert abs(g.course_spacing_mm - 100/24) < 1e-12
    x=project_grid(1200,1800,g)
    assert x.stitches == 216
    assert x.rows == 432
    assert abs(x.achieved_width_mm-1200) < 1e-9
    assert abs(x.achieved_height_mm-1800) < 1e-9
