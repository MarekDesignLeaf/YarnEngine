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
    states=[
      ("INTERIOR_BUILDING","OPERATOR"),("INTERIOR_VALIDATING","ORCHESTRATOR"),
      ("INTERIOR_APPROVED","DECISION_ENGINE"),("INTERIOR_LOCKED","ORCHESTRATOR"),
      ("COVER_BUILDING","ORCHESTRATOR"),("COVER_VALIDATING","ORCHESTRATOR"),
      ("COVER_APPROVED","DECISION_ENGINE"),("COVER_LOCKED","ORCHESTRATOR"),
      ("FINAL_VALIDATING","ORCHESTRATOR"),("RELEASE_APPROVED","DECISION_ENGINE"),
      ("EXPORTING","ORCHESTRATOR"),("EXPORTED","ORCHESTRATOR")
    ]
    for state,role in states:
        e=s.transition(e["id"],state,"tester",actor_role=role)
    assert e["state"]=="EXPORTED"
    events=s.events(e["id"])
    assert len(events)==1+len(states)
    assert events[-1]["to_state"]=="EXPORTED"


def test_failed_catalogue_requires_correction(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    path=[
      ("INTERIOR_BUILDING","OPERATOR"),("INTERIOR_VALIDATING","ORCHESTRATOR"),
      ("INTERIOR_FAILED","DECISION_ENGINE"),("INTERIOR_BUILDING","ORCHESTRATOR"),
      ("INTERIOR_VALIDATING","ORCHESTRATOR")
    ]
    for state,role in path:
        trigger="route_failure" if e["state"]=="INTERIOR_FAILED" and state=="INTERIOR_BUILDING" else None
        e=s.transition(e["id"],state,"tester",actor_role=role,trigger=trigger)
    assert e["state"]=="INTERIOR_VALIDATING"


def test_release_is_blocked_without_explicit_gates(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    path=[
      ("INTERIOR_BUILDING","OPERATOR"),("INTERIOR_VALIDATING","ORCHESTRATOR"),
      ("INTERIOR_APPROVED","DECISION_ENGINE"),("INTERIOR_LOCKED","ORCHESTRATOR"),
      ("COVER_BUILDING","ORCHESTRATOR"),("COVER_VALIDATING","ORCHESTRATOR"),
      ("COVER_APPROVED","DECISION_ENGINE"),("COVER_LOCKED","ORCHESTRATOR"),
      ("FINAL_VALIDATING","ORCHESTRATOR")
    ]
    for state,role in path:e=s.transition(e["id"],state,"tester",actor_role=role)
    with pytest.raises(ValueError, match="approvals"):
        s.transition(e["id"],"RELEASE_APPROVED","tester",actor_role="DECISION_ENGINE")
    s.add_approval(e["id"],"IP_DISCLOSURE","NOT_APPLICABLE","RELEASE_AUTHORITY",actor="tester")
    s.add_approval(e["id"],"COMPLIANCE","APPROVED","RELEASE_AUTHORITY","evidence:1",actor="tester")
    assert s.transition(e["id"],"RELEASE_APPROVED","tester",actor_role="DECISION_ENGINE")["state"]=="RELEASE_APPROVED"


def test_validation_is_bound_to_binary_hash(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    a=s.create_asset(e["id"],"PAGE",1,"asset.html","abc123","tester")
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
    a=s.create_asset(e["id"],"PAGE",1,"view.html","v1","tester")
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


def _identity_record(name="Fox"):
    return {"product_id":"P1","variant_id":"V1","display_name":name,
            "mandatory_features":{"ears":2,"tails":1,"legs":4},
            "handed_features":{"heart":"left_chest"},
            "silhouette_class":"fox","pattern_topology":"striped",
            "material_class":"crochet","colours":["orange","white"]}


def _identity_observation(ears=2):
    return {"features":{"ears":ears,"tails":1,"legs":4},
            "handed_features":{"heart":"left_chest"},
            "silhouette_class":"fox","pattern_topology":"striped",
            "material_class":"crochet","colours":["orange","white"]}


def test_master_visual_requires_validation_before_lock(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite");e=s.create(manifest(),"tester")
    pm=s.create_product_master(1,_identity_record(),"pm1","tester");s.approve_product_master(pm["id"],"tester")
    a=s.create_asset(e["id"],"MASTER_VISUAL",1,"fox.png","asset-hash","tester",source_record_version="1")
    with pytest.raises(ValueError,match="PASS validation"):s.lock_master_visual(a["id"],"tester")
    r=s.validate_product_identity(a["id"],_identity_observation(),"tester")
    assert r["decision"]=="PASS"
    assert s.lock_master_visual(a["id"],"tester")["state"]=="LOCKED"


def test_identity_validator_catches_extra_ear(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite");e=s.create(manifest(),"tester")
    pm=s.create_product_master(1,_identity_record(),"pm1","tester");s.approve_product_master(pm["id"],"tester")
    a=s.create_asset(e["id"],"MASTER_VISUAL",1,"bad.png","bad-hash","tester",source_record_version="1")
    r=s.validate_product_identity(a["id"],_identity_observation(ears=3),"tester")
    assert r["decision"]=="FAIL"
    assert any(x["id"]=="FEATURE_COUNT:ears" and x["status"]=="FAIL" for x in r["checks"])


def test_product_view_requires_locked_master_and_canonical_token(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite");e=s.create(manifest(),"tester")
    pm=s.create_product_master(1,_identity_record(),"pm1","tester");s.approve_product_master(pm["id"],"tester")
    mv=s.create_asset(e["id"],"MASTER_VISUAL",1,"fox.png","mv","tester",source_record_version="1")
    s.validate_product_identity(mv["id"],_identity_observation(),"tester");s.lock_master_visual(mv["id"],"tester")
    with pytest.raises(ValueError,match="canonical view_token"):
        s.create_asset(e["id"],"PRODUCT_VIEW",1,"x.png","x","tester",{"master_visual_id":mv["id"],"view_token":"SIDE"},"1")
    v=s.create_asset(e["id"],"PRODUCT_VIEW",1,"front.png","front","tester",
                     {"master_visual_id":mv["id"],"view_token":"AZ000","observation":{
                       "identity_key":"P1/V1","feature_signature":"2e-1t-4l","material_signature":"crochet",
                       "colour_signature":"orange-white","pattern_signature":"striped"}},"1")
    assert v["metadata"]["azimuth_deg"]==0


def test_multiview_graph_is_fail_closed_until_complete(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite");e=s.create(manifest(),"tester")
    pm=s.create_product_master(1,_identity_record(),"pm1","tester");s.approve_product_master(pm["id"],"tester")
    mv=s.create_asset(e["id"],"MASTER_VISUAL",1,"fox.png","mv","tester",source_record_version="1")
    s.validate_product_identity(mv["id"],_identity_observation(),"tester");s.lock_master_visual(mv["id"],"tester")
    obs={"identity_key":"P1/V1","feature_signature":"2e-1t-4l","material_signature":"crochet",
         "colour_signature":"orange-white","pattern_signature":"striped"}
    for token in ("AZ000","AZ045"):
        s.create_asset(e["id"],"PRODUCT_VIEW",1,token+".png",token,"tester",
                       {"master_visual_id":mv["id"],"view_token":token,"observation":obs},"1")
    r=s.validate_view_consistency(e["id"],1,"tester")
    assert r["decision"]=="BLOCKED"
    assert "AZ090" in r["missing_views"]


def test_release_approvals_are_bound_to_exact_manifest_hash(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    s.add_approval(e["id"],"IP_DISCLOSURE","NOT_APPLICABLE","RELEASE_AUTHORITY",actor="tester")
    s.add_approval(e["id"],"COMPLIANCE","APPROVED","RELEASE_AUTHORITY",actor="tester")
    assert s.release_gates_ok(e["id"]) is True
    with s._conn() as db:
        changed={**e["manifest"],"subtitle":"changed after approval"}
        db.execute("UPDATE catalogue_editions SET manifest_json=? WHERE id=?",
                   (__import__("json").dumps(changed,separators=(",",":")),e["id"]))
    assert s.release_gates_ok(e["id"]) is False


def test_release_timestamp_is_written_only_at_released(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(manifest(),"tester")
    s.add_approval(e["id"],"IP_DISCLOSURE","NOT_APPLICABLE","RELEASE_AUTHORITY",actor="tester")
    s.add_approval(e["id"],"COMPLIANCE","NOT_APPLICABLE","RELEASE_AUTHORITY",actor="tester")
    path=[
      ("INTERIOR_BUILDING","OPERATOR"),("INTERIOR_VALIDATING","ORCHESTRATOR"),
      ("INTERIOR_APPROVED","DECISION_ENGINE"),("INTERIOR_LOCKED","ORCHESTRATOR"),
      ("COVER_BUILDING","ORCHESTRATOR"),("COVER_VALIDATING","ORCHESTRATOR"),
      ("COVER_APPROVED","DECISION_ENGINE"),("COVER_LOCKED","ORCHESTRATOR"),
      ("FINAL_VALIDATING","ORCHESTRATOR"),("RELEASE_APPROVED","DECISION_ENGINE"),
      ("EXPORTING","ORCHESTRATOR"),("EXPORTED","ORCHESTRATOR")
    ]
    for state,role in path:e=s.transition(e["id"],state,"tester",actor_role=role)
    assert e["approved_at"] and e["exported_at"] and e["released_at"] is None
    e=s.transition(e["id"],"RELEASED","tester",actor_role="RELEASE_AUTHORITY")
    assert e["released_at"] is not None
