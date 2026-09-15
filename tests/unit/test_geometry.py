from math import pi
from src.geometry.ciukas import single_bar_needle_loop_mm, horizontal_float_mm, plain_loop_path_mm

def test_published_formula_components():
    A,B,d=5.0,4.0,1.0
    ls=0.5*pi*(0.5*A+d)+2*B
    lh=0.5*pi*(0.5*A+d)
    assert abs(single_bar_needle_loop_mm(A,B,d)-ls) < 1e-12
    assert abs(horizontal_float_mm(A,d,2)-lh) < 1e-12
    assert abs(plain_loop_path_mm(A,B,d)-(ls+lh)) < 1e-12
