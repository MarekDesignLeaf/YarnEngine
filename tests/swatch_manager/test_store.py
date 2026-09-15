from src.swatch_manager.store import SwatchStore
def test_swatch_crud(tmp_path):
 s=SwatchStore(tmp_path/"s.sqlite")
 d={"name":"S1","pattern_id":"P","pattern_version":"1","yarn_id":"Y","stitches":20,"rows":30,"width_cm":10,"height_cm":10,"yarn_length_m":7}
 x=s.create(d);assert x["swatch_id"]>0 and len(s.list())==1
 assert s.delete(x["swatch_id"]);s.close()
