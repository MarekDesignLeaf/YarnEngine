from src.projects.store import ProjectStore
def calc():
    return {"pattern_id":"STOCKINETTE","pattern_version":"1.0.0","yarn_id":None,"width_cm":50}
def test_create_get_update_delete(tmp_path):
    s=ProjectStore(tmp_path/"p.sqlite")
    try:
        p=s.create("Test",None,"STOCKINETTE","1.0.0",None,calc(),{"x":1},"calculated")
        assert p["name"]=="Test"
        q=s.update(p["project_id"],name="Renamed",status="archived")
        assert q["name"]=="Renamed" and q["status"]=="archived"
        assert len(s.list())==1
        assert s.delete(p["project_id"]) is True
        assert s.get(p["project_id"]) is None
    finally:s.close()
