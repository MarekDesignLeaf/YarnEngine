from src.projects.store import ProjectStore,request_fingerprint

REQ={"pattern_id":"P","pattern_version":"1","width_cm":10}
def test_request_change_invalidates_result(tmp_path):
 s=ProjectStore(tmp_path/"p.sqlite")
 p=s.create("x",None,"P","1",None,REQ,{"answer":1},"calculated")
 assert p["result"] is not None and not p["result_stale"]
 q={**REQ,"width_cm":20}
 p=s.update(p["project_id"],request=q)
 assert p["result"] is None and p["result_request_hash"] is None
 assert p["request_hash"]==request_fingerprint(q)

def test_matching_result_hash(tmp_path):
 s=ProjectStore(tmp_path/"p.sqlite")
 p=s.create("x",None,"P","1",None,REQ,None)
 p=s.update(p["project_id"],result={"answer":2})
 assert not p["result_stale"] and p["result_request_hash"]==p["request_hash"]
