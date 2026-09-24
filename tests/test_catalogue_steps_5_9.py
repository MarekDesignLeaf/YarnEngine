import json
import pytest

from src.catalogue.store import CatalogueStore
from src.catalogue.providers import DeterministicFixtureProvider, GenerationRequest
from src.catalogue.correction import choose_correction
from src.catalogue.decision import decide
from src.catalogue.composer import compose_product_page
from src.catalogue.interior import InteriorBuilder


def _master_record():
    return {
        "product_id":"P1","variant_id":"V1","display_name":"Fox",
        "mandatory_features":{"ears":2},"handed_features":{"heart":"left_chest"},
        "silhouette_class":"fox","pattern_topology":"striped",
        "material_class":"crochet","colours":["orange","white"],
        "description":"Canonical fox"
    }


def _observation():
    return {
        "features":{"ears":2},"handed_features":{"heart":"left_chest"},
        "silhouette_class":"fox","pattern_topology":"striped",
        "material_class":"crochet","colours":["orange","white"]
    }


def _edition_manifest():
    return {
        "title":"Test","subtitle":"","locale":"en-GB","format":"A4",
        "products":[{"product_line_id":1,"name":"Fox","description":"Catalogue fox"}]
    }


def _locked_master_visual(store, edition_id):
    pm=store.create_product_master(1,_master_record(),"pm-hash","tester")
    pm=store.approve_product_master(pm["id"],"tester")
    mv=store.create_asset(edition_id,"MASTER_VISUAL",1,"fox.png","mv-hash","tester",
                          source_record_version=str(pm["version"]))
    store.validate_product_identity(mv["id"],_observation(),"tester")
    return store.lock_master_visual(mv["id"],"tester")


def test_provider_is_candidate_only_and_deterministic():
    p=DeterministicFixtureProvider()
    req=GenerationRequest("PRODUCT_VIEW",1,"1","make canonical view",(),{"view":"AZ000"})
    a=p.generate(req);b=p.generate(req)
    assert a.candidate_sha256==b.candidate_sha256
    assert a.provider_id=="fixture"
    assert not hasattr(a,"decision")
    assert not hasattr(a,"approved")


def test_decision_engine_known_fail_precedence():
    policy={"policy_id":"p","policy_version":"1","required_check_ids":["A","B"]}
    results=[
      {"id":"A","status":"FAIL","evidence":{"x":1},"method":"EXACT"},
      {"id":"B","status":"NOT_RUN"}
    ]
    r=decide(policy,results)
    assert r["decision"]=="FAIL"


def test_decision_engine_blocks_untrusted_not_applicable():
    policy={"policy_id":"p","policy_version":"1","required_check_ids":["A"]}
    r=decide(policy,[{"id":"A","status":"NOT_APPLICABLE","assigned_by":"AI"}])
    assert r["decision"]=="BLOCKED"


def test_decision_engine_requires_current_calibration():
    policy={"policy_id":"p","policy_version":"1","required_check_ids":["A"]}
    result={"id":"A","status":"PASS","evidence":{"region":[0,0,1,1]},
            "method":"CALIBRATED_AI","calibration_id":"c1","validator_version":"2",
            "calibration_validator_version":"1"}
    assert decide(policy,[result])["decision"]=="BLOCKED"
    result["calibration_validator_version"]="2"
    assert decide(policy,[result])["decision"]=="PASS"


def test_correction_hierarchy_reaches_human_review():
    failed=[{"id":"CROP","status":"FAIL","scope":"LOCAL"}]
    p1=choose_correction(10,failed,[])
    assert p1.action=="LOCAL_EDIT"
    p2=choose_correction(10,failed,[{"action":"LOCAL_EDIT"}])
    assert p2.action=="CONSTRAINED_REGENERATION"
    p3=choose_correction(10,failed,[{"action":"LOCAL_EDIT"},{"action":"CONSTRAINED_REGENERATION"}])
    assert p3.action=="FULL_REGENERATION"
    p4=choose_correction(10,failed,[{"action":"LOCAL_EDIT"},{"action":"CONSTRAINED_REGENERATION"},
                                   {"action":"FULL_REGENERATION"}])
    assert p4.action=="HUMAN_REVIEW"


def test_page_composer_is_byte_deterministic():
    product={"product_id":"P1","variant_id":"V1","display_name":"Fox","description":"Text"}
    visual={"state":"LOCKED","sha256":"mv","uri":"fox.png"}
    brand={"logo_uri":"logo.png","logo_sha256":"logo"}
    a=compose_product_page(page_number=1,product=product,master_visual=visual,brand=brand)
    b=compose_product_page(page_number=1,product=product,master_visual=visual,brand=brand)
    assert a.html==b.html
    assert a.sha256==b.sha256
    assert b'page-number">1<' in a.html
    assert b'P1' in a.html


def test_interior_builder_uses_only_locked_current_master_visual(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(_edition_manifest(),"tester")
    _locked_master_visual(s,e["id"])
    builder=InteriorBuilder(s,tmp_path/"out")
    result=builder.build(e["id"],{"logo_uri":"logo.png","logo_sha256":"logo-hash"},"tester")
    assert len(result["pages"])==1
    page=s.get_asset(result["pages"][0]["asset_id"])
    assert page["asset_type"]=="PAGE"
    assert page["state"]=="CANDIDATE"
    assert (tmp_path/"out"/str(e["id"])/"page_0001.html").exists()
    raw=json.loads((tmp_path/"out"/str(e["id"])/"interior_manifest.json").read_text())
    assert raw["pages"][0]["sha256"]==page["sha256"]


def test_store_decision_engine_sets_review_state(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(_edition_manifest(),"tester")
    a=s.create_asset(e["id"],"PAGE",1,"p.html","hash","tester")
    policy={"policy_id":"page","policy_version":"1","required_check_ids":["A"]}
    out=s.decide_and_add_validation(a["id"],policy,[{"id":"A","status":"UNCERTAIN"}],"tester")
    assert out["decision"]=="NEEDS_REVIEW"
    assert s.get_asset(a["id"])["state"]=="HUMAN_REVIEW"


def test_correction_candidate_must_be_new_asset(tmp_path):
    s=CatalogueStore(tmp_path/"catalogue.sqlite")
    e=s.create(_edition_manifest(),"tester")
    parent=s.create_asset(e["id"],"PAGE",1,"p1.html","h1","tester")
    plan=s.plan_correction(parent["id"],[{"id":"TEXT","status":"FAIL","scope":"LOCAL"}],"tester")
    with pytest.raises(ValueError,match="new candidate"):
        s.attach_correction_candidate(plan["correction_id"],parent["id"])
    candidate=s.create_asset(e["id"],"PAGE",1,"p2.html","h2","tester")
    assert s.attach_correction_candidate(plan["correction_id"],candidate["id"])["id"]==candidate["id"]
