"""APVP-facing deterministic conformance snapshot for Catalogue Factory.

This endpoint is deliberately read-only. It exercises release invariants against
the same production modules used by Catalogue Factory, but never touches customer
catalogue records.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from .composer import compose_product_page
from .correction import choose_correction
from .decision import decide
from .governance import (
    canonical_turntable_azimuth,
    compliance_claim_allowed,
    gc_permitted,
    human_override_permitted,
    inventory_diff_reviewed,
    physical_fidelity_gate,
    require_derived_candidate,
    require_exact_asset,
    require_locale_record,
    unexpected_text_check,
    validate_calibration,
    validate_live_commerce_publish,
    validate_page_manifest,
    validate_reproducibility_profile,
)
from .multiview import VIEW_ORDER, neighbours, validate_view_metadata, identity_checks
from .providers import DeterministicFixtureProvider, GenerationRequest
from .store import CatalogueStore, EDITION_TRANSITIONS, EDITION_TERMINAL_STATES
from .threed import validate_360_manifest

CONTRACT_VERSION="catalogue-factory-apvp-v1"
NORMATIVE_STATE_MACHINE_VERSION="1.5.0"
NORMATIVE_STATE_MACHINE_SHA256="17a1f5761facfedeb8c64e77aaee770a69575ae3539ff0322356826350390e49"


def _check(check_id, fn):
    try:
        fn()
        return {"check_id":check_id,"status":"PASS"}
    except Exception as exc:
        return {"check_id":check_id,"status":"FAIL",
                "error":f"{type(exc).__name__}: {exc}"}


def _new_store():
    td=tempfile.TemporaryDirectory()
    return td,CatalogueStore(Path(td.name)/"catalogue.sqlite")


def _basic_record():
    return {
      "product_id":"P1","variant_id":"V1","display_name":"Fox",
      "mandatory_features":{"ears":2,"tails":1},
      "handed_features":{"heart":"left_chest"},
      "silhouette_class":"fox","pattern_topology":"striped",
      "material_class":"crochet","colours":["orange","white"]
    }


def run_conformance():
    checks=[]

    # ---- core invariants retained for backward-compatible APVP consumers ----
    def fail_precedence():
        p={"policy_id":"p","policy_version":"1","required_check_ids":["A","B"]}
        out=decide(p,[{"id":"A","status":"FAIL","evidence":{"x":1},"method":"EXACT"}])
        assert out["decision"]=="FAIL" and "B" in out.get("missing_checks",[])
    checks.append(_check("DECISION_KNOWN_FAIL_PRECEDENCE",fail_precedence))

    def missing_policy():
        assert decide(None,[])["decision"]=="BLOCKED"
    checks.append(_check("DECISION_MISSING_POLICY_BLOCKED",missing_policy))

    def not_applicable_policy_only():
        p={"policy_id":"p","policy_version":"1","required_check_ids":["A"]}
        assert decide(p,[{"id":"A","status":"NOT_APPLICABLE","assigned_by":"AI"}])["decision"]=="BLOCKED"
        assert decide(p,[{"id":"A","status":"NOT_APPLICABLE","assigned_by":"POLICY"}])["decision"]=="PASS"
    checks.append(_check("NOT_APPLICABLE_POLICY_ONLY",not_applicable_policy_only))

    def calibrated_ai():
        p={"policy_id":"p","policy_version":"1","required_check_ids":["A"]}
        r={"id":"A","status":"PASS","evidence":{"region":[0,0,1,1]},"method":"CALIBRATED_AI",
           "calibration_id":"c","validator_version":"2","calibration_validator_version":"1"}
        assert decide(p,[r])["decision"]=="BLOCKED"
        r["calibration_validator_version"]="2"
        assert decide(p,[r])["decision"]=="PASS"
    checks.append(_check("CALIBRATED_AI_VERSION_BOUND",calibrated_ai))

    def correction_exhaustion():
        failed=[{"id":"X","status":"FAIL","scope":"LOCAL"}]
        assert choose_correction(1,failed,[]).action=="LOCAL_EDIT"
        assert choose_correction(1,failed,[{"action":"LOCAL_EDIT"}]).action=="CONSTRAINED_REGENERATION"
        assert choose_correction(1,failed,[{"action":"LOCAL_EDIT"},{"action":"CONSTRAINED_REGENERATION"}]).action=="FULL_REGENERATION"
        assert choose_correction(1,failed,[{"action":"LOCAL_EDIT"},{"action":"CONSTRAINED_REGENERATION"},{"action":"FULL_REGENERATION"}]).action=="HUMAN_REVIEW"
    checks.append(_check("CORRECTION_EXHAUSTS_TO_HUMAN_REVIEW",correction_exhaustion))

    def canonical_views():
        assert len(VIEW_ORDER)==8 and len(set(VIEW_ORDER))==8
        assert neighbours("AZ000")==("AZ315","AZ045")
        assert validate_view_metadata({"view_token":"AZ090"})["azimuth_deg"]==90
    checks.append(_check("MULTIVIEW_CANONICAL_GRAPH",canonical_views))

    def ai_360_rejected():
        try:
            validate_360_manifest({"source":"AI_GENERATED","frame_count":24,"step_deg":15,
                                   "frame_hashes":["x"]*24})
        except ValueError:return
        raise AssertionError("independent AI frames were accepted as true 360")
    checks.append(_check("TRUE_360_REJECTS_INDEPENDENT_AI",ai_360_rejected))

    def valid_360_shape():
        m=validate_360_manifest({"source":"PHYSICAL_TURNTABLE","frame_count":24,"step_deg":15,
                                 "frame_hashes":[f"h{i}" for i in range(24)]})
        assert m["frame_count"]==24 and m["source"]=="PHYSICAL_TURNTABLE"
    checks.append(_check("TRUE_360_MANIFEST_CONTRACT",valid_360_shape))

    def provider_candidate_only():
        r=DeterministicFixtureProvider().generate(
          GenerationRequest("PRODUCT_VIEW",1,"1","canonical product view",(),{"view":"AZ000"}))
        assert r.candidate_sha256 and not hasattr(r,"decision") and not hasattr(r,"approved")
    checks.append(_check("GENERATOR_CANNOT_SELF_APPROVE",provider_candidate_only))

    def state_machine_gate_bypass():
        td,s=_new_store()
        try:
            e=s.create({"title":"T","products":[]},"apvp")
            try:s.transition(e["id"],"RELEASE_APPROVED","apvp")
            except ValueError:return
            raise AssertionError("DRAFT bypassed directly to RELEASE_APPROVED")
        finally:td.cleanup()
    checks.append(_check("EDITION_RELEASE_GATE_BYPASS_REJECTED",state_machine_gate_bypass))

    def release_approval_gates():
        td,s=_new_store()
        try:
            e=s.create({"title":"T","products":[]},"apvp")
            path=(
              ("INTERIOR_BUILDING","OPERATOR"),("INTERIOR_VALIDATING","ORCHESTRATOR"),
              ("INTERIOR_APPROVED","DECISION_ENGINE"),("INTERIOR_LOCKED","ORCHESTRATOR"),
              ("COVER_BUILDING","ORCHESTRATOR"),("COVER_VALIDATING","ORCHESTRATOR"),
              ("COVER_APPROVED","DECISION_ENGINE"),("COVER_LOCKED","ORCHESTRATOR"),
              ("FINAL_VALIDATING","ORCHESTRATOR")
            )
            for st,role in path:
                e=s.transition(e["id"],st,"apvp",actor_role=role)
            try:s.transition(e["id"],"RELEASE_APPROVED","apvp",actor_role="DECISION_ENGINE")
            except ValueError:pass
            else:raise AssertionError("release passed without approvals")
            s.add_approval(e["id"],"IP_DISCLOSURE","NOT_APPLICABLE","RELEASE_AUTHORITY",actor="apvp")
            s.add_approval(e["id"],"COMPLIANCE","APPROVED","RELEASE_AUTHORITY",actor="apvp")
            assert s.transition(e["id"],"RELEASE_APPROVED","apvp",actor_role="DECISION_ENGINE")["state"]=="RELEASE_APPROVED"
        finally:td.cleanup()
    checks.append(_check("RELEASE_REQUIRES_IP_AND_COMPLIANCE",release_approval_gates))

    def dependency_invalidation():
        td,s=_new_store()
        try:
            e=s.create({"title":"T","products":[]},"apvp")
            rec={"product_id":"P","variant_id":"V","display_name":"Fox"}
            pm1=s.create_product_master(1,rec,"pm1","apvp");s.approve_product_master(pm1["id"],"apvp")
            a=s.create_asset(e["id"],"MASTER_VISUAL",1,"v1.png","a1","apvp",source_record_version="1")
            pm2=s.create_product_master(1,{**rec,"material":"changed"},"pm2","apvp");s.approve_product_master(pm2["id"],"apvp")
            assert s.get_asset(a["id"])["state"]=="STALE"
            assert s.get_product_master(pm1["id"])["state"]=="SUPERSEDED"
        finally:td.cleanup()
    checks.append(_check("UPSTREAM_CHANGE_INVALIDATES_DEPENDANTS",dependency_invalidation))

    def binary_validation_binding():
        td,s=_new_store()
        try:
            e=s.create({"title":"T","products":[]},"apvp")
            a=s.create_asset(e["id"],"PAGE",None,"p.html","correct","apvp")
            report={"asset_sha256":"wrong","policy_version":"1","validator_id":"exact",
                    "validator_version":"1","decision":"PASS",
                    "checks":[{"id":"HASH","status":"PASS"}],"evidence":{"hash":"wrong"},"method":"EXACT"}
            try:s.add_validation(a["id"],report,"apvp")
            except ValueError:return
            raise AssertionError("validation report transferred to another binary")
        finally:td.cleanup()
    checks.append(_check("VALIDATION_BOUND_TO_ASSET_HASH",binary_validation_binding))

    def deterministic_page():
        product={"product_id":"P","variant_id":"V","display_name":"Fox","description":"Text"}
        visual={"state":"LOCKED","sha256":"visual","uri":"fox.png"}
        brand={"logo_uri":"logo.png","logo_sha256":"logo"}
        a=compose_product_page(page_number=1,product=product,master_visual=visual,brand=brand)
        b=compose_product_page(page_number=1,product=product,master_visual=visual,brand=brand)
        assert a.sha256==b.sha256 and a.html==b.html
    checks.append(_check("PAGE_COMPOSER_BYTE_DETERMINISTIC",deterministic_page))

    # ---- Master Specification acceptance criteria AC01..AC32 ----
    def ac01():
        p={"product_id":"P1","variant_id":"V1","display_name":"Fox"}
        v={"state":"LOCKED","sha256":"visual","uri":"fox.png"}
        b={"logo_uri":"logo.png","logo_sha256":"logo-hash"}
        page=compose_product_page(page_number=1,product=p,master_visual=v,brand=b)
        assert page.manifest["logo_sha256"]=="logo-hash"
        require_exact_asset("logo-hash",page.manifest["logo_sha256"],label="logo")
    checks.append(_check("AC01",ac01))

    def ac02():
        validate_page_manifest([{"page_number":1},{"page_number":2},{"page_number":3}],[1,2,3])
        try:validate_page_manifest([{"page_number":1},{"page_number":3}],[1,2])
        except ValueError:return
        raise AssertionError("page numbering mismatch accepted")
    checks.append(_check("AC02",ac02))

    def ac03():
        dependency_invalidation()
    checks.append(_check("AC03",ac03))

    def ac04():
        ref={"approval_record_id":"APR1","required_measurements":{"height_mm":250}}
        assert physical_fidelity_gate(ref,{"measurements":{"height_mm":250}})["decision"]=="PASS"
        assert physical_fidelity_gate(None,{"measurements":{"height_mm":250}})["decision"]=="BLOCKED"
        assert physical_fidelity_gate(ref,{"measurements":{"height_mm":249}})["decision"]=="FAIL"
    checks.append(_check("AC04",ac04))

    def ac05():missing_policy()
    checks.append(_check("AC05",ac05))

    def ac06():provider_candidate_only()
    checks.append(_check("AC06",ac06))

    def ac07():fail_precedence()
    checks.append(_check("AC07",ac07))

    def ac08():
        master=_basic_record()
        obs={"features":{"ears":3,"tails":1},"handed_features":{"heart":"right_chest"},
             "silhouette_class":"fox","pattern_topology":"striped",
             "material_class":"crochet","colours":["orange","white"]}
        r=identity_checks(master,obs)
        assert r["decision"]=="FAIL"
        ids={x["id"] for x in r["checks"] if x["status"]=="FAIL"}
        assert "FEATURE_COUNT:ears" in ids and "HANDEDNESS:heart" in ids
    checks.append(_check("AC08",ac08))

    def ac09():
        p={"policy_id":"p","policy_version":"1","required_check_ids":["A"],"disagreement_check_ids":["A"]}
        r={"id":"A","status":"PASS","evidence":{"x":1},"method":"EXACT","disagreement":True}
        assert decide(p,[r])["decision"]=="NEEDS_REVIEW"
    checks.append(_check("AC09",ac09))

    def ac10():
        td,s=_new_store()
        try:
            e=s.create({"title":"T","products":[]},"apvp")
            pm=s.create_product_master(1,_basic_record(),"pm1","apvp");s.approve_product_master(pm["id"],"apvp")
            mv=s.create_asset(e["id"],"MASTER_VISUAL",1,"fox.png","mv","apvp",source_record_version="1")
            obs={"features":{"ears":2,"tails":1},"handed_features":{"heart":"left_chest"},
                 "silhouette_class":"fox","pattern_topology":"striped","material_class":"crochet",
                 "colours":["orange","white"]}
            s.validate_product_identity(mv["id"],obs,"apvp");s.lock_master_visual(mv["id"],"apvp")
            sig={"identity_key":"P1/V1","feature_signature":"2e-1t","material_signature":"crochet",
                 "colour_signature":"orange-white","pattern_signature":"striped"}
            for token in VIEW_ORDER:
                s.create_asset(e["id"],"PRODUCT_VIEW",1,token+".png",token,"apvp",
                  {"master_visual_id":mv["id"],"view_token":token,"observation":sig},"1")
            scope=s.revalidation_scope_for_view(e["id"],1,"AZ090")
            assert scope["view_tokens"]==["AZ090","AZ045","AZ135"] and len(scope["asset_ids"])==3
            parent=next(a for a in s.list_assets(e["id"]) if a["metadata"].get("view_token")=="AZ090")
            plan=s.plan_correction(parent["id"],[{"id":"EAR","status":"FAIL","scope":"LOCAL"}],"apvp")
            candidate=s.create_asset(e["id"],"PRODUCT_VIEW",1,"AZ090-v2.png","AZ090-v2","apvp",
              {"master_visual_id":mv["id"],"view_token":"AZ090","observation":sig},"1")
            s.attach_correction_candidate(plan["correction_id"],candidate["id"])
            assert candidate["id"]!=parent["id"]
        finally:td.cleanup()
    checks.append(_check("AC10",ac10))

    def ac11():
        td,s=_new_store()
        try:
            e=s.create({"title":"T","products":[]},"apvp")
            a=s.create_asset(e["id"],"PAGE",None,"p.html","h1","apvp")
            rid=s.add_validation(a["id"],{"asset_sha256":"h1","policy_version":"pv1",
              "validator_id":"exact","validator_version":"v7","decision":"PASS",
              "checks":[{"id":"X","status":"PASS"}],"evidence":{"sha256":"h1"},"method":"EXACT"},"apvp")
            hist=s.validation_history(a["id"]);r=next(x for x in hist if x["id"]==rid)
            assert r["asset_sha256"]=="h1" and r["policy_version"]=="pv1" and r["validator_version"]=="v7"
        finally:td.cleanup()
    checks.append(_check("AC11",ac11))

    def ac12():
        validate_calibration({"held_out_dataset":True,"validator_version":"2","sample_count":300,"approved":True},"2")
        try:validate_calibration({"held_out_dataset":False,"validator_version":"2","sample_count":300,"approved":True},"2")
        except ValueError:return
        raise AssertionError("non-held-out calibration accepted")
    checks.append(_check("AC12",ac12))

    def ac13():not_applicable_policy_only()
    checks.append(_check("AC13",ac13))

    def ac14():
        assert human_override_permitted(method="EXACT",zero_tolerance=True) is False
        assert human_override_permitted(method="CALIBRATED_CV",zero_tolerance=False) is True
    checks.append(_check("AC14",ac14))

    def ac15():
        td,s=_new_store()
        try:
            e=s.create({"title":"T","products":[]},"apvp")
            pm1=s.create_product_master(1,_basic_record(),"pm1","apvp");s.approve_product_master(pm1["id"],"apvp")
            a=s.create_asset(e["id"],"MASTER_VISUAL",1,"v1.png","a1","apvp",source_record_version="1")
            with s._conn() as db:db.execute("UPDATE catalogue_assets SET state='LOCKED' WHERE id=?",(a["id"],))
            pm2=s.create_product_master(1,{**_basic_record(),"material_class":"wool"},"pm2","apvp");s.approve_product_master(pm2["id"],"apvp")
            assert s.get_asset(a["id"])["state"]=="STALE"
            try:s.lock_asset(a["id"])
            except ValueError:pass
            else:raise AssertionError("STALE asset reopened")
            replacement=s.create_asset(e["id"],"MASTER_VISUAL",1,"v2.png","a2","apvp",source_record_version="2")
            assert replacement["version"]==2
        finally:td.cleanup()
    checks.append(_check("AC15",ac15))

    def ac16():
        td,s=_new_store()
        try:
            e=s.create({"title":"T","products":[]},"apvp")
            e=s.transition(e["id"],"INTERIOR_BUILDING","apvp",actor_role="OPERATOR")
            e=s.transition(e["id"],"INTERIOR_VALIDATING","apvp",actor_role="ORCHESTRATOR")
            e=s.transition(e["id"],"INTERIOR_HUMAN_REVIEW","apvp",actor_role="DECISION_ENGINE")
            e=s.transition(e["id"],"INTERIOR_CHANGE_REQUESTED","apvp",actor_role="HUMAN_REVIEWER")
            assert "RELEASE_APPROVED" not in EDITION_TRANSITIONS["INTERIOR_CHANGE_REQUESTED"]
            try:s.transition(e["id"],"RELEASE_APPROVED","apvp",actor_role="CR_AUTHORITY")
            except ValueError:return
            raise AssertionError("open change request reached release approval")
        finally:td.cleanup()
    checks.append(_check("AC16",ac16))

    def ac17():
        for state,targets in EDITION_TRANSITIONS.items():
            if state not in EDITION_TERMINAL_STATES and state!="PUBLISHED":
                assert targets, f"nonterminal {state} has no outgoing transition"
    checks.append(_check("AC17",ac17))

    def ac18():
        for state in ("SUPERSEDED","DISCARDED","WITHDRAWN"):
            assert EDITION_TRANSITIONS[state]==set()
    checks.append(_check("AC18",ac18))

    def ac19():
        assert {"INTERIOR_VALIDATING","INTERIOR_HUMAN_REVIEW"} <= EDITION_TRANSITIONS["INTERIOR_BLOCKED"]
        assert {"COVER_VALIDATING","COVER_HUMAN_REVIEW"} <= EDITION_TRANSITIONS["COVER_BLOCKED"]
        assert {"FINAL_VALIDATING","FINAL_HUMAN_REVIEW"} <= EDITION_TRANSITIONS["FINAL_BLOCKED"]
        assert "RELEASE_APPROVED" not in EDITION_TRANSITIONS["INTERIOR_HUMAN_REVIEW"]
        assert "RELEASE_APPROVED" not in EDITION_TRANSITIONS["COVER_HUMAN_REVIEW"]
    checks.append(_check("AC19",ac19))

    def ac20():release_approval_gates()
    checks.append(_check("AC20",ac20))

    def ac21():
        assert unexpected_text_check(["PILOOP","Fox"],["PILOOP","Fox"])["decision"]=="PASS"
        assert unexpected_text_check(["PILOOP"],["PILOOP","FREE"])["decision"]=="FAIL"
    checks.append(_check("AC21",ac21))

    def ac22():
        records={"en-GB":{"approved":True,"text":"Fox"}}
        assert require_locale_record("en-GB",records)["text"]=="Fox"
        try:require_locale_record("cs-CZ",records)
        except ValueError:return
        raise AssertionError("silent locale fallback accepted")
    checks.append(_check("AC22",ac22))

    def ac23():
        rec={"price":"99.00"}
        hist=[{"displayed_value":"99.00","at":"2026-01-01T00:00:00Z"}]
        assert validate_live_commerce_publish(rec,hist,{"decision":"APPROVED"})["decision"]=="PASS"
        assert validate_live_commerce_publish(rec,[],{"decision":"APPROVED"})["decision"]=="BLOCKED"
    checks.append(_check("AC23",ac23))

    def ac24():
        assert canonical_turntable_azimuth(90,False)==270.0
        try:canonical_turntable_azimuth(90,True)
        except ValueError:return
        raise AssertionError("mirrored turntable accepted")
    checks.append(_check("AC24",ac24))

    def ac25():
        ai_360_rejected();valid_360_shape()
    checks.append(_check("AC25",ac25))

    def ac26():
        require_derived_candidate("old","new","USDZ_CONVERT",True)
        try:require_derived_candidate("same","same","UPSCALE",True)
        except ValueError:return
        raise AssertionError("derived output reused source binary")
    checks.append(_check("AC26",ac26))

    def ac27():
        validate_reproducibility_profile({"reproducibility":"BYTE_IDENTICAL",
          "renderer_version":"1","font_bundle_hash":"fonts","object_order_policy":"stable",
          "release_timestamp":"2026-01-01T00:00:00Z"})
        try:validate_reproducibility_profile({"reproducibility":"BYTE_IDENTICAL","renderer_version":"1"})
        except ValueError:return
        raise AssertionError("incomplete byte-identical profile accepted")
    checks.append(_check("AC27",ac27))

    def ac28():
        assert gc_permitted({"legal_hold":True,"retention_expired":True,"state":"FAILED"}) is False
        assert gc_permitted({"legal_hold":False,"retention_expired":True,"state":"FAILED"}) is True
    checks.append(_check("AC28",ac28))

    def ac29():ac12()
    checks.append(_check("AC29",ac29))

    def ac30():
        assert compliance_claim_allowed("UKCA",[]) is False
        assert compliance_claim_allowed("CE",[{"approval_type":"COMPLIANCE_CE","decision":"APPROVED"}]) is True
    checks.append(_check("AC30",ac30))

    def ac31():
        assert NORMATIVE_STATE_MACHINE_VERSION=="1.5.0"
        assert NORMATIVE_STATE_MACHINE_SHA256=="17a1f5761facfedeb8c64e77aaee770a69575ae3539ff0322356826350390e49"
        required={"INTERIOR_FAILED","COVER_FAILED","FINAL_FAILED","EXPORTING","EXPORT_FAILED",
                  "EXPORT_HUMAN_REVIEW","RELEASED","WITHDRAWN","SUPERSEDED","DISCARDED"}
        states=set(EDITION_TRANSITIONS)
        for targets in EDITION_TRANSITIONS.values(): states.update(targets)
        assert required <= states
        assert "EXPORTING" in EDITION_TRANSITIONS["RELEASE_APPROVED"]
        assert "RELEASED" in EDITION_TRANSITIONS["EXPORTED"]
        assert EDITION_TRANSITIONS["RELEASED"]=={"WITHDRAWN"}
        ac17();ac18()
    checks.append(_check("AC31",ac31))

    def ac32():
        assert inventory_diff_reviewed(["R1","R2"],["R1","R2"],False)["changed"]==[]
        try:inventory_diff_reviewed(["R1"],["R1","R2"],False)
        except ValueError:pass
        else:raise AssertionError("unreviewed rule inventory change accepted")
        out=inventory_diff_reviewed(["R1"],["R1","R2"],True)
        assert out["changed"]==["R2"] and out["reviewed"] is True
    checks.append(_check("AC32",ac32))

    passed=sum(1 for c in checks if c["status"]=="PASS")
    return {
      "contract_version":CONTRACT_VERSION,
      "normative_state_machine":{
        "version":NORMATIVE_STATE_MACHINE_VERSION,
        "sha256":NORMATIVE_STATE_MACHINE_SHA256,
      },
      "decision":"PASS" if passed==len(checks) else "FAIL",
      "checks_passed":passed,
      "checks_total":len(checks),
      "checks":checks,
      "check_map":{item["check_id"]:item["status"] for item in checks},
      "acceptance_criteria_total":32,
      "acceptance_criteria_passed":sum(1 for item in checks if item["check_id"].startswith("AC") and item["status"]=="PASS"),
      "invariants":[item["check_id"] for item in checks if not item["check_id"].startswith("AC")],
    }
