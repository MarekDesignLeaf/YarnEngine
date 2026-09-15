from pathlib import Path
from src.pattern_engine.loader import load_pattern_file
from src.pattern_engine.registry import load_operation_registry
from src.pattern_editor.convert import canonical_to_editor,editor_to_canonical_dict
from src.pattern_editor.validation import validate_editor_grid
from src.pattern_editor.edit import paint_cell
ROOT=Path(__file__).resolve().parents[2]
def test_stockinette_roundtrip_editor():
    ops=load_operation_registry(ROOT/"data/stitches/operations.seed.json")
    p=load_pattern_file(ROOT/"data/patterns/stockinette.json")
    e=canonical_to_editor(p,ops)
    assert e.width==1 and e.height==2
    assert validate_editor_grid(e,ops)==()
    d=editor_to_canonical_dict(e)
    assert d["repeat"]["width_stitches"]==1
def test_paint_operation():
    ops=load_operation_registry(ROOT/"data/stitches/operations.seed.json")
    p=load_pattern_file(ROOT/"data/patterns/stockinette.json")
    e=canonical_to_editor(p,ops)
    e2=paint_cell(e,1,1,"P",ops)
    assert any(c.operation_id=="P" and c.row==1 for c in e2.cells)
