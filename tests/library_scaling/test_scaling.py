from src.library_scaling.pipeline import structural_signature,portfolio_report,scale_gate
from src.library_scaling.batch import inspect_scaling_batch
OPS={"K":{"consumes_stitches":1,"produces_stitches":1},"P":{"consumes_stitches":1,"produces_stitches":1}}
def b(pid,op="K",license="INTERNAL"):
 return {"pattern":{"pattern_id":pid,"version":"1","name":pid,"technique":"knitting",
 "repeat":{"width_stitches":4,"height_rows":1},"rows":[{"row":1,"side":"RS","sequence":[{"op":op,"n":4}]}]},
 "metadata":{"pattern_id":pid,"version":"1","name":pid,"family_id":"TEST","tags":[],"difficulty":"basic",
 "techniques":["knitting"],"source_type":"internal","source_reference":"test","license_id":license,"active":True}}
def test_signature_ignores_identity():
 assert structural_signature(b("A")["pattern"])==structural_signature(b("B")["pattern"])
def test_signature_detects_structure_change():
 assert structural_signature(b("A","K")["pattern"])!=structural_signature(b("A","P")["pattern"])
def test_portfolio_duplicates():
 r=portfolio_report([b("A"),b("B")]);assert r["distinct_structures"]==1 and len(r["structural_duplicate_groups"])==1
def test_gate_does_not_fake_target():
 r=scale_gate([b("A")],100);assert not r["ready"] and r["issues"][0]["code"]=="TARGET_NOT_REACHED"
def test_license_gate():
 r=scale_gate([b("A",license=None)],1);assert not r["ready"] and any(x["code"]=="LICENSE_REVIEW_REQUIRED" for x in r["issues"])
def test_batch_flags_structural_duplicate():
 r=inspect_scaling_batch([b("A"),b("B")],OPS)
 assert r["valid"]==2 and r["reports"][1]["structural_duplicate"]["batch_index"]==0
