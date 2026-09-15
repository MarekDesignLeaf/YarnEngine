from src.shaping.loader import load_shaped_pattern_dict
from src.spatial_shaping.topology import build_spatial_topology,topology_profile,approximate_2d_outline
from src.spatial_shaping.service import analyse_spatial_shaping

OPS={
"K":{"consumes_stitches":1,"produces_stitches":1},
"KFB":{"consumes_stitches":1,"produces_stitches":2},
"K2TOG":{"consumes_stitches":2,"produces_stitches":1},
}

def pattern():
 return load_shaped_pattern_dict({"pattern_id":"T","version":"1","name":"T","initial_stitches":4,"rows":[
 {"row":1,"side":"RS","sequence":[{"op":"KFB","n":1},{"op":"K","n":2},{"op":"KFB","n":1}]},
 {"row":2,"side":"WS","sequence":[{"op":"K","n":6}]},
 {"row":3,"side":"RS","sequence":[{"op":"K2TOG","n":1},{"op":"K","n":2},{"op":"K2TOG","n":1}]}
 ]})

def test_spatial_positions_and_deltas():
 t=build_spatial_topology(pattern(),OPS)
 assert t["valid"] and t["final_stitches"]==4
 assert t["rows"][0]["delta"]==2 and len(t["rows"][0]["shaping_events"])==2
 assert t["rows"][2]["delta"]==-2 and len(t["rows"][2]["shaping_events"])==2

def test_profile_contains_positions():
 p=topology_profile(build_spatial_topology(pattern(),OPS))
 assert len(p["rows"][0]["increase_positions"])==2
 assert len(p["rows"][2]["decrease_positions"])==2

def test_outline_uses_supplied_gauge():
 o=approximate_2d_outline(build_spatial_topology(pattern(),OPS),4,3)
 assert o["valid"]
 assert o["points_right"][0]["x_mm"]==12
 assert o["points_right"][0]["y_mm"]==3

def test_service_with_outline():
 payload={"pattern_id":"T","name":"T","initial_stitches":4,
 "gauge_preview":{"stitch_width_mm":4,"row_height_mm":3},
 "rows":[{"instruction":"KFB, K2, KFB"},{"instruction":"K6"},{"instruction":"K2TOG, K2, K2TOG"}]}
 r=analyse_spatial_shaping(payload,OPS)
 assert r["valid"] and r["outline"]["valid"]

def test_invalid_continuity_does_not_build_topology():
 payload={"pattern_id":"T","name":"T","initial_stitches":4,
 "rows":[{"instruction":"KFB, K2, KFB"},{"instruction":"K4"}]}
 r=analyse_spatial_shaping(payload,OPS)
 assert not r["valid"] and r["topology"] is None
