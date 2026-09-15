from src.domain.units import *
def test_tex_roundtrip():
    assert abs(tex_from_metres_per_100g(200)-500) < 1e-12
    assert abs(metres_per_100g_from_tex(500)-200) < 1e-12
def test_mass():
    assert abs(mass_g_from_length_m(200,500)-100) < 1e-12
def test_packages():
    assert packages_required(401,200)==3
