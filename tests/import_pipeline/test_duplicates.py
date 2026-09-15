import json
from pathlib import Path
from src.import_pipeline.duplicates import duplicate_pattern_groups,near_duplicate_yarns
ROOT=Path(__file__).resolve().parents[2]
def test_exact_pattern_duplicate_detection():
    d=json.loads((ROOT/"data/patterns/stockinette.json").read_text())
    d2=json.loads(json.dumps(d)); d2["pattern_id"]="STOCKINETTE_COPY"
    groups=duplicate_pattern_groups([d,d2])
    assert len(groups)==1
def test_near_duplicate_yarn_candidates():
    y=json.loads((ROOT/"data/yarns/TEST_Y1.json").read_text())
    y2=dict(y); y2["yarn_id"]="OTHER"
    g=near_duplicate_yarns([y,y2])
    assert len(g)==1
