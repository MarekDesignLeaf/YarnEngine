from src.stitch_groups.engine import load_events,apply_events
from src.stitch_groups.service import analyse_stitch_groups

def run(events,initial=12):
 return apply_events(initial,load_events(events))

def test_split_preserves_total():
 r=run([{"step":1,"action":"split","source_ids":["G0"],"target_ids":["L","R"],"counts":[5,7]}])
 assert r["valid"] and r["live_stitches"]==12
 assert r["groups"]["L"]["stitches"]==5 and r["groups"]["R"]["stitches"]==7

def test_split_mismatch_rejected():
 r=run([{"step":1,"action":"split","source_ids":["G0"],"target_ids":["L","R"],"counts":[5,6]}])
 assert not r["valid"] and r["issues"][0]["code"]=="SPLIT_COUNT_MISMATCH"

def test_hold_resume():
 r=run([
 {"step":1,"action":"split","source_ids":["G0"],"target_ids":["L","R"],"counts":[6,6]},
 {"step":2,"action":"hold","source_ids":["R"]},
 {"step":3,"action":"resume","source_ids":["R"]},
 ])
 assert r["valid"] and r["groups"]["R"]["state"]=="active"

def test_join_two_groups():
 r=run([
 {"step":1,"action":"split","source_ids":["G0"],"target_ids":["L","R"],"counts":[6,6]},
 {"step":2,"action":"join","source_ids":["L","R"],"target_ids":["BODY"]},
 ])
 assert r["valid"] and r["groups"]["BODY"]["stitches"]==12
 assert r["groups"]["L"]["state"]=="closed" and r["groups"]["R"]["state"]=="closed"

def test_join_held_group_allowed():
 r=run([
 {"step":1,"action":"split","source_ids":["G0"],"target_ids":["L","R"],"counts":[6,6]},
 {"step":2,"action":"hold","source_ids":["R"]},
 {"step":3,"action":"join","source_ids":["L","R"],"target_ids":["BODY"]},
 ])
 assert r["valid"] and r["groups"]["BODY"]["stitches"]==12

def test_close_removes_live_stitches():
 r=run([{"step":1,"action":"close","source_ids":["G0"]}])
 assert r["valid"] and r["live_stitches"]==0

def test_service_bad_model():
 r=analyse_stitch_groups({"initial_stitches":12,"events":[{"step":1,"action":"nonsense"}]})
 assert not r["valid"] and r["issues"][0]["code"]=="GROUP_MODEL_ERROR"
