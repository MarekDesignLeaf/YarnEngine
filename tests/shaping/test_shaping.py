from src.shaping.loader import load_shaped_pattern_dict
from src.shaping.validation import validate_shaped_pattern
from src.shaping.service import translate_shaping

OPS={
"K":{"consumes_stitches":1,"produces_stitches":1},
"KFB":{"consumes_stitches":1,"produces_stitches":2},
"K2TOG":{"consumes_stitches":2,"produces_stitches":1},
"YO":{"consumes_stitches":0,"produces_stitches":1},
}

def test_increase_then_decrease_trace():
 p={"pattern_id":"S","version":"1","name":"S","initial_stitches":4,"rows":[
 {"row":1,"side":"RS","sequence":[{"op":"KFB","n":1},{"op":"K","n":3}]},
 {"row":2,"side":"WS","sequence":[{"op":"K2TOG","n":1},{"op":"K","n":3}]}
 ]}
 r=validate_shaped_pattern(load_shaped_pattern_dict(p),OPS)
 assert r["valid"] and r["final_stitches"]==4
 assert [x["delta"] for x in r["trace"]]==[1,-1]

def test_row_continuity_failure():
 p={"pattern_id":"S","version":"1","name":"S","initial_stitches":4,"rows":[
 {"row":1,"side":"RS","sequence":[{"op":"KFB","n":1},{"op":"K","n":3}]},
 {"row":2,"side":"WS","sequence":[{"op":"K","n":4}]}
 ]}
 r=validate_shaped_pattern(load_shaped_pattern_dict(p),OPS)
 assert not r["valid"] and any(x["code"]=="ROW_INPUT_MISMATCH" for x in r["issues"])

def test_declared_counts_checked():
 p={"pattern_id":"S","version":"1","name":"S","initial_stitches":4,"rows":[
 {"row":1,"side":"RS","expected_in":4,"expected_out":99,"sequence":[{"op":"K","n":4}]}
 ]}
 r=validate_shaped_pattern(load_shaped_pattern_dict(p),OPS)
 assert any(x["code"]=="DECLARED_OUTPUT_MISMATCH" for x in r["issues"])

def test_translate_shaping_valid():
 p={"pattern_id":"S","name":"S","initial_stitches":4,
 "rows":[{"instruction":"KFB, K3"},{"instruction":"K2TOG, K3"}]}
 r=translate_shaping(p,OPS)
 assert r["valid"] and r["final_stitches"]==4

def test_translate_shaping_bad_second_row():
 p={"pattern_id":"S","name":"S","initial_stitches":4,
 "rows":[{"instruction":"KFB, K3"},{"instruction":"K4"}]}
 r=translate_shaping(p,OPS)
 assert not r["valid"] and any(x["code"]=="ROW_INPUT_MISMATCH" for x in r["issues"])

def test_zero_initial_rejected():
 r=translate_shaping({"pattern_id":"S","initial_stitches":0,"rows":[]},OPS)
 assert not r["valid"] and r["issues"][0]["code"]=="INITIAL_STITCHES_REQUIRED"
