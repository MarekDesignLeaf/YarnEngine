import pytest
from src.catalogue.store import CatalogueStore


def manifest():
    return {"title":"Test","subtitle":"","locale":"en-GB","format":"A4","products":[]}


def test_catalogue_state_machine_is_fail_closed(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    assert e["state"]=="DRAFT"
    with pytest.raises(ValueError):
        s.transition(e["id"],"RELEASE_APPROVED","tester")
    assert s.get(e["id"])["state"]=="DRAFT"


def test_catalogue_happy_path_and_audit(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    s.add_approval(e["id"],"IP_DISCLOSURE","NOT_APPLICABLE","tester")
    s.add_approval(e["id"],"COMPLIANCE","NOT_APPLICABLE","tester")
    states=["INTERIOR_BUILDING","INTERIOR_VALIDATING","INTERIOR_LOCKED","COVER_BUILDING",
            "COVER_VALIDATING","FINAL_VALIDATING","RELEASE_APPROVED","EXPORTED"]
    for state in states:
        e=s.transition(e["id"],state,"tester")
    assert e["state"]=="EXPORTED"
    events=s.events(e["id"])
    assert len(events)==1+len(states)
    assert events[-1]["to_state"]=="EXPORTED"


def test_failed_catalogue_requires_correction(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    for state in ["INTERIOR_BUILDING","INTERIOR_VALIDATING","FAILED","CORRECTING","INTERIOR_VALIDATING"]:
        e=s.transition(e["id"],state,"tester")
    assert e["state"]=="INTERIOR_VALIDATING"


def test_release_is_blocked_without_explicit_gates(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    for state in ["INTERIOR_BUILDING","INTERIOR_VALIDATING","INTERIOR_LOCKED","COVER_BUILDING",
                  "COVER_VALIDATING","FINAL_VALIDATING"]:
        e=s.transition(e["id"],state,"tester")
    with pytest.raises(ValueError, match="approvals"):
        s.transition(e["id"],"RELEASE_APPROVED","tester")
    s.add_approval(e["id"],"IP_DISCLOSURE","NOT_APPLICABLE","tester")
    s.add_approval(e["id"],"COMPLIANCE","APPROVED","compliance-owner","evidence:1")
    assert s.transition(e["id"],"RELEASE_APPROVED","tester")["state"]=="RELEASE_APPROVED"


def test_validation_is_bound_to_binary_hash(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    a=s.create_asset(e["id"],"MASTER_VISUAL",1,"asset.png","abc123","tester")
    report={"asset_sha256":"wrong","policy_version":"1","validator_id":"hash-check",
            "validator_version":"1","decision":"PASS","checks":[{"id":"HASH","status":"PASS"}],
            "evidence":{"sha256":"wrong"},"method":"EXACT"}
    with pytest.raises(ValueError, match="hash mismatch"):
        s.add_validation(a["id"],report,"tester")
    report["asset_sha256"]="abc123"; report["evidence"]={"sha256":"abc123"}
    s.add_validation(a["id"],report,"tester")
    assert s.get_asset(a["id"])["state"]=="VALIDATED"


def test_ai_pass_requires_calibration(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    a=s.create_asset(e["id"],"PRODUCT_VIEW",1,"view.png","v1","tester")
    report={"asset_sha256":"v1","policy_version":"1","validator_id":"vision",
            "validator_version":"2","decision":"PASS","checks":[{"id":"IDENTITY","status":"PASS"}],
            "evidence":{"region":[0,0,1,1]},"method":"AI"}
    with pytest.raises(ValueError, match="calibration_id"):
        s.add_validation(a["id"],report,"tester")


def test_product_master_change_marks_old_dependent_asset_stale(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    pm1=s.create_product_master(7,{"product_id":"P7","variant_id":"V1","display_name":"Fox"},"hash-pm1","tester")
    pm1=s.approve_product_master(pm1["id"],"tester")
    a=s.create_asset(e["id"],"MASTER_VISUAL",7,"fox-v1.png","asset1","tester",
                     source_record_version=str(pm1["version"]))
    assert s.get_asset(a["id"])["state"]=="CANDIDATE"
    pm2=s.create_product_master(7,{"product_id":"P7","variant_id":"V1","display_name":"Fox",
                                  "materials":["new"]},"hash-pm2","tester")
    s.approve_product_master(pm2["id"],"tester")
    assert s.get_asset(a["id"])["state"]=="STALE"
    assert s.get_product_master(pm1["id"])["state"]=="SUPERSEDED"
    assert s.get_product_master(pm2["id"])["state"]=="APPROVED"


def test_locked_asset_is_not_reopened_after_master_change(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    pm1=s.create_product_master(9,{"product_id":"P9","variant_id":"V1","display_name":"Bear"},"h1","tester")
    s.approve_product_master(pm1["id"],"tester")
    a=s.create_asset(e["id"],"MASTER_VISUAL",9,"bear.png","a1","tester",source_record_version="1")
    # Simulate an approved/locked production binary. Invalidation may only mark it stale.
    with s._conn() as db: db.execute("UPDATE catalogue_assets SET state='LOCKED' WHERE id=?",(a["id"],))
    pm2=s.create_product_master(9,{"product_id":"P9","variant_id":"V1","display_name":"Bear 2"},"h2","tester")
    s.approve_product_master(pm2["id"],"tester")
    assert s.get_asset(a["id"])["state"]=="STALE"
    # A replacement is a new asset version, never the old binary reopened.
    replacement=s.create_asset(e["id"],"MASTER_VISUAL",9,"bear-v2.png","a2","tester",source_record_version="2")
    assert replacement["version"]==2
    assert replacement["state"]=="CANDIDATE"
