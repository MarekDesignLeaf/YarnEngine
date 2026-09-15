from pathlib import Path
from src.project_geometry.model import *
from src.project_geometry.planner import *
from src.project_geometry.expand import expand_project
from src.pattern_engine.loader import load_pattern_file
from src.pattern_engine.registry import load_operation_registry
ROOT=Path(__file__).resolve().parents[2]
OPS=load_operation_registry(ROOT/"data/stitches/operations.seed.json")
def test_exact_with_edges():
    h=plan_horizontal(100,8,EdgeZone(2,2),PartialRepeatMode.REJECT)
    assert h.full_repeats==12 and h.accounted_stitches==100
def test_split_partial():
    h=plan_horizontal(103,8,EdgeZone(2,2),PartialRepeatMode.SPLIT)
    assert (h.partial_left,h.partial_right)==(1,2) and h.accounted_stitches==103
def test_vertical():
    v=plan_vertical(27,4); assert (v.full_repeats,v.partial_rows)==(6,3)
def test_rib_project():
    p=load_pattern_file(ROOT/"data/patterns/rib_2x2.json")
    x=expand_project(p,OPS,15,4,EdgeZone(1,1),PartialRepeatMode.SPLIT)
    assert x["horizontal_layout"].accounted_stitches==15
    assert len(x["row_operation_counts"])==4
def test_cable_partial_rejected_when_cut():
    p=load_pattern_file(ROOT/"data/patterns/cable_2x2_simple.json")
    try: expand_project(p,OPS,5,4,EdgeZone(),PartialRepeatMode.RIGHT)
    except ValueError: pass
    else: raise AssertionError("unsafe cable cut should fail")
