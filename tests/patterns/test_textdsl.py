from pathlib import Path
from src.pattern_parser.textdsl import parse_pattern_text
from src.pattern_engine.registry import load_operation_registry
from src.pattern_engine.validation import validate_pattern

ROOT=Path(__file__).resolve().parents[2]

def test_dsl_parser():
    text=(ROOT/"data/patterns/example_cable.pattern").read_text()
    p=parse_pattern_text(text)
    assert p.repeat_width_stitches==8
    assert p.repeat_height_rows==4
    ops=load_operation_registry(ROOT/"data/stitches/operations.seed.json")
    report=validate_pattern(p,ops)
    assert report.valid, report.issues
