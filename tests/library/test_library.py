from pathlib import Path
from src.library.loader import load_library
from src.library.search import search_yarns,search_patterns
from src.library.compatibility import assess_yarn_for_gauge
ROOT=Path(__file__).resolve().parents[2]
def test_load_library():
    r=load_library(ROOT)
    assert len(r.yarns)>=2 and "TEST_Y1" in r.yarns
    assert len(r.patterns)>=7
def test_search_yarn():
    r=load_library(ROOT)
    x=search_yarns(r,cyc_weight=4)
    assert len(x)>=1 and any(y.yarn_id=="TEST_Y1" for y in x)
def test_search_pattern():
    r=load_library(ROOT)
    x=search_patterns(r,family_id="CABLE",tags=("cable",))
    assert len(x)>=1 and any(p.pattern_id=="CABLE_2X2_SIMPLE" for p in x)
def test_tex_derived():
    r=load_library(ROOT)
    assert abs(r.yarns["TEST_Y1"].derived_tex-500)<1e-9
def test_compatibility_screen():
    r=load_library(ROOT)
    x=assess_yarn_for_gauge(r.yarns["TEST_Y1"],18,5.0)
    assert x.compatible
    assert any("swatch" in w for w in x.warnings)
