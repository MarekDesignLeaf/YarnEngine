from pathlib import Path
from src.pattern_engine.loader import load_pattern_file
from src.pattern_engine.registry import load_operation_registry
from src.pattern_engine.validation import validate_pattern
from src.pattern_engine.expand import expand_full_repeats
from src.pattern_engine.analyse import operation_counts_per_repeat

ROOT=Path(__file__).resolve().parents[2]
OPS=load_operation_registry(ROOT/"data/stitches/operations.seed.json")

def test_all_json_patterns_validate():
    files=list((ROOT/"data/patterns").glob("*.json"))
    assert len(files)>=7
    for f in files:
        report=validate_pattern(load_pattern_file(f),OPS)
        assert report.valid, (f.name, report.issues)

def test_expand_stockinette():
    p=load_pattern_file(ROOT/"data/patterns/stockinette.json")
    x=expand_full_repeats(p,10,20)
    assert x.full_repeats_x==10
    assert x.full_repeats_y==10
    assert x.operation_counts["K"]==100
    assert x.operation_counts["P"]==100

def test_cable_repeat_counts():
    p=load_pattern_file(ROOT/"data/patterns/cable_2x2_simple.json")
    c=operation_counts_per_repeat(p)
    assert c["C2_2R"]==1
    assert c["P"]==16
    assert c["K"]==12

def test_reject_partial_repeat():
    p=load_pattern_file(ROOT/"data/patterns/rib_2x2.json")
    try:
        expand_full_repeats(p,10,20)
    except ValueError as e:
        assert "not divisible" in str(e)
    else:
        raise AssertionError("expected ValueError")
