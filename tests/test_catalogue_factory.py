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
