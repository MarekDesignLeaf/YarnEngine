from src.branch_knitting.engine import execute_branch_program
from src.pattern_engine.registry import load_operation_registry
from pathlib import Path
OPS=load_operation_registry(Path(__file__).resolve().parents[2]/"data/stitches/operations.seed.json")

def test_independent_branches_and_join():
 p={"initial_stitches":12,"steps":[
 {"type":"split","group":"G0","targets":[{"id":"L","stitches":6},{"id":"R","stitches":6}]},
 {"type":"hold","group":"R"},
 {"type":"row","group":"L","instruction":"K6"},
 {"type":"row","group":"L","instruction":"P6"},
 {"type":"hold","group":"L"},
 {"type":"activate","group":"R"},
 {"type":"row","group":"R","instruction":"K6"},
 {"type":"activate","group":"L"},
 {"type":"join","groups":["L","R"],"target":"BODY"}]}
 r=execute_branch_program(p,OPS)
 assert r["valid"] and r["groups"]["BODY"]["stitches"]==12
 assert r["operation_counts"]["K"]==12 and r["operation_counts"]["P"]==6

def test_cannot_work_held_group():
 p={"initial_stitches":6,"steps":[{"type":"hold","group":"G0"},{"type":"row","group":"G0","instruction":"K6"}]}
 r=execute_branch_program(p,OPS)
 assert not r["valid"] and any(x["code"]=="ROW_GROUP_NOT_ACTIVE" for x in r["issues"])

def test_shaping_inside_branch():
 p={"initial_stitches":4,"steps":[{"type":"row","group":"G0","instruction":"KFB, K3"}]}
 r=execute_branch_program(p,OPS)
 assert r["valid"] and r["groups"]["G0"]["stitches"]==5 and r["operation_counts"]["KFB"]==1

def test_bad_split_rejected():
 p={"initial_stitches":10,"steps":[{"type":"split","group":"G0","targets":[{"id":"A","stitches":4},{"id":"B","stitches":5}]}]}
 r=execute_branch_program(p,OPS)
 assert not r["valid"]
