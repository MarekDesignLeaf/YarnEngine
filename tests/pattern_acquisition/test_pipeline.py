from src.pattern_acquisition.pipeline import acquire_structured_text
OPS={"K":{"consumes_stitches":1,"produces_stitches":1},"P":{"consumes_stitches":1,"produces_stitches":1}}
def base():
 return {"pattern_id":"ACQ_TEST","name":"Acq","repeat":{"width_stitches":4,"height_rows":2},
 "rows":[{"row":1,"side":"RS","instruction":"K4"},{"row":2,"side":"WS","instruction":"P4"}],
 "metadata":{"family_id":"PLAIN","difficulty":"basic","techniques":["knitting"],"source_type":"user_import",
 "source_reference":"test","license_id":"TEST_ONLY"}}
def test_pipeline_to_import_review():
 r=acquire_structured_text(base(),OPS,[])
 assert r["valid"] and r["stage"]=="import_review"
def test_pipeline_supports_width_bounded_repeat():
 x=base();x["rows"][0]["instruction"]="K2, P2, repeat to end"
 r=acquire_structured_text(x,OPS,[])
 assert r["valid"] and r["stage"]=="import_review"

def test_pipeline_stops_on_non_tiling_repeat():
 x=base();x["repeat"]["width_stitches"]=6;x["rows"][0]["instruction"]="K2, P2, repeat to end"
 r=acquire_structured_text(x,OPS,[])
 assert not r["valid"] and r["stage"]=="translation_review"
