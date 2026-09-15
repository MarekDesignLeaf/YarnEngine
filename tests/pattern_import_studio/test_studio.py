from src.pattern_import_studio.studio import normalize_bundle,inspect_bundle,batch_inspect
OPS={"K":{"consumes_stitches":1,"produces_stitches":1}}
def good():
 return {"pattern":{"pattern_id":"my test","version":"1.0.0","name":"My Test","repeat":{"width_stitches":2,"height_rows":1},
 "rows":[{"sequence":[{"op":"k","n":2}]}]},"metadata":{"family_id":"plain","source_type":"user_import","source_reference":"local:test","license_id":"OWNED"}}
def test_normalize_and_validate():
 r=inspect_bundle(good(),OPS,[]);assert r["valid"] and r["bundle"]["pattern"]["pattern_id"]=="MY_TEST"
def test_unknown_operation_invalid():
 x=good();x["pattern"]["rows"][0]["sequence"][0]["op"]="BAD"
 assert not inspect_bundle(x,OPS,[])["valid"]
def test_duplicate_identity():
 r=inspect_bundle(good(),OPS,[{"pattern_id":"MY_TEST","version":"1.0.0","checksum":"x"}])
 assert r["duplicate"]["type"]=="identity_conflict"
def test_batch():
 r=batch_inspect([good(),good()],OPS,[]);assert r["total"]==2 and r["valid"]==2
