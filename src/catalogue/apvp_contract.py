"""APVP-facing deterministic conformance snapshot for Catalogue Factory.

This module performs no database writes and exposes no customer/product data.
It is safe to call repeatedly from an external validation platform.
"""
from __future__ import annotations
from .decision import decide
from .correction import choose_correction
from .multiview import VIEW_ORDER, neighbours, validate_view_metadata
from .threed import validate_360_manifest
from .providers import DeterministicFixtureProvider, GenerationRequest
from .composer import compose_product_page
from .store import CatalogueStore
import tempfile
from pathlib import Path

CONTRACT_VERSION="catalogue-factory-apvp-v1"


def _check(check_id, fn):
    try:
        fn()
        return {"check_id":check_id,"status":"PASS"}
    except Exception as exc:
        return {"check_id":check_id,"status":"FAIL",
                "error":f"{type(exc).__name__}: {exc}"}


def run_conformance():
    checks=[]

    def fail_precedence():
        policy={"policy_id":"p","policy_version":"1","required_check_ids":["A","B"]}
        out=decide(policy,[{"id":"A","status":"FAIL","evidence":{"x":1},"method":"EXACT"}])
        assert out["decision"]=="FAIL"
        assert "B" in out.get("missing_checks",[])
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
        f=[{"id":"X","status":"FAIL","scope":"LOCAL"}]
        p1=choose_correction(1,f,[]);assert p1.action=="LOCAL_EDIT"
        p2=choose_correction(1,f,[{"action":"LOCAL_EDIT"}]);assert p2.action=="CONSTRAINED_REGENERATION"
        p3=choose_correction(1,f,[{"action":"LOCAL_EDIT"},{"action":"CONSTRAINED_REGENERATION"}]);assert p3.action=="FULL_REGENERATION"
        p4=choose_correction(1,f,[{"action":"LOCAL_EDIT"},{"action":"CONSTRAINED_REGENERATION"},{"action":"FULL_REGENERATION"}]);assert p4.action=="HUMAN_REVIEW"
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
        except ValueError:
            return
        raise AssertionError("independent AI frames were accepted as true 360")
    checks.append(_check("TRUE_360_REJECTS_INDEPENDENT_AI",ai_360_rejected))

    def valid_360_shape():
        m=validate_360_manifest({"source":"PHYSICAL_TURNTABLE","frame_count":24,"step_deg":15,
                                 "frame_hashes":[f"h{i}" for i in range(24)]})
        assert m["frame_count"]==24 and m["source"]=="PHYSICAL_TURNTABLE"
    checks.append(_check("TRUE_360_MANIFEST_CONTRACT",valid_360_shape))

    def provider_candidate_only():
        provider=DeterministicFixtureProvider()
        req=GenerationRequest("PRODUCT_VIEW",1,"1","canonical product view",(),{"view":"AZ000"})
        result=provider.generate(req)
        assert result.candidate_sha256
        assert not hasattr(result,"decision") and not hasattr(result,"approved")
    checks.append(_check("GENERATOR_CANNOT_SELF_APPROVE",provider_candidate_only))

    def state_machine_gate_bypass():
        with tempfile.TemporaryDirectory() as td:
            store=CatalogueStore(Path(td)/"catalogue.sqlite")
            edition=store.create({"title":"T","products":[]},"apvp")
            try:
                store.transition(edition["id"],"RELEASE_APPROVED","apvp")
            except ValueError:
                return
            raise AssertionError("DRAFT bypassed directly to RELEASE_APPROVED")
    checks.append(_check("EDITION_RELEASE_GATE_BYPASS_REJECTED",state_machine_gate_bypass))

    def release_approval_gates():
        with tempfile.TemporaryDirectory() as td:
            store=CatalogueStore(Path(td)/"catalogue.sqlite")
            e=store.create({"title":"T","products":[]},"apvp")
            for state in ("INTERIOR_BUILDING","INTERIOR_VALIDATING","INTERIOR_LOCKED",
                          "COVER_BUILDING","COVER_VALIDATING","FINAL_VALIDATING"):
                e=store.transition(e["id"],state,"apvp")
            blocked=False
            try: store.transition(e["id"],"RELEASE_APPROVED","apvp")
            except ValueError: blocked=True
            assert blocked
            store.add_approval(e["id"],"IP_DISCLOSURE","NOT_APPLICABLE","apvp")
            store.add_approval(e["id"],"COMPLIANCE","APPROVED","apvp")
            assert store.transition(e["id"],"RELEASE_APPROVED","apvp")["state"]=="RELEASE_APPROVED"
    checks.append(_check("RELEASE_REQUIRES_IP_AND_COMPLIANCE",release_approval_gates))

    def dependency_invalidation():
        with tempfile.TemporaryDirectory() as td:
            store=CatalogueStore(Path(td)/"catalogue.sqlite")
            e=store.create({"title":"T","products":[]},"apvp")
            record={"product_id":"P","variant_id":"V","display_name":"Fox"}
            pm1=store.create_product_master(1,record,"pm1","apvp");store.approve_product_master(pm1["id"],"apvp")
            a=store.create_asset(e["id"],"MASTER_VISUAL",1,"v1.png","a1","apvp",source_record_version="1")
            pm2=store.create_product_master(1,{**record,"material":"changed"},"pm2","apvp")
            store.approve_product_master(pm2["id"],"apvp")
            assert store.get_asset(a["id"])["state"]=="STALE"
            assert store.get_product_master(pm1["id"])["state"]=="SUPERSEDED"
    checks.append(_check("UPSTREAM_CHANGE_INVALIDATES_DEPENDANTS",dependency_invalidation))

    def binary_validation_binding():
        with tempfile.TemporaryDirectory() as td:
            store=CatalogueStore(Path(td)/"catalogue.sqlite")
            e=store.create({"title":"T","products":[]},"apvp")
            a=store.create_asset(e["id"],"PAGE",None,"p.html","correct","apvp")
            report={"asset_sha256":"wrong","policy_version":"1","validator_id":"exact",
                    "validator_version":"1","decision":"PASS",
                    "checks":[{"id":"HASH","status":"PASS"}],"evidence":{"hash":"wrong"},"method":"EXACT"}
            try: store.add_validation(a["id"],report,"apvp")
            except ValueError: return
            raise AssertionError("validation report transferred to a different binary hash")
    checks.append(_check("VALIDATION_BOUND_TO_ASSET_HASH",binary_validation_binding))

    def deterministic_page():
        product={"product_id":"P","variant_id":"V","display_name":"Fox","description":"Text"}
        visual={"state":"LOCKED","sha256":"visual","uri":"fox.png"}
        brand={"logo_uri":"logo.png","logo_sha256":"logo"}
        a=compose_product_page(page_number=1,product=product,master_visual=visual,brand=brand)
        b=compose_product_page(page_number=1,product=product,master_visual=visual,brand=brand)
        assert a.sha256==b.sha256 and a.html==b.html
    checks.append(_check("PAGE_COMPOSER_BYTE_DETERMINISTIC",deterministic_page))

    passed=sum(1 for c in checks if c["status"]=="PASS")
    return {
      "contract_version":CONTRACT_VERSION,
      "decision":"PASS" if passed==len(checks) else "FAIL",
      "checks_passed":passed,
      "checks_total":len(checks),
      "checks":checks,
      "check_map":{item["check_id"]:item["status"] for item in checks},
      "invariants":[
        "generation_provider_cannot_approve",
        "missing_policy_blocks",
        "not_applicable_policy_only",
        "calibrated_ai_bound_to_validator_version",
        "correction_exhausts_to_human_review",
        "canonical_multiview_graph",
        "true_360_requires_canonical_3d_or_physical_turntable",
        "generation_provider_cannot_approve",
        "edition_release_gate_bypass_rejected",
        "release_requires_ip_and_compliance",
        "upstream_change_invalidates_dependants",
        "validation_bound_to_asset_hash",
        "page_composer_byte_deterministic"
      ]
    }
