"""APVP-facing deterministic conformance snapshot for Catalogue Factory.

This module performs no database writes and exposes no customer/product data.
It is safe to call repeatedly from an external validation platform.
"""
from __future__ import annotations
from .decision import decide
from .correction import choose_correction
from .multiview import VIEW_ORDER, neighbours, validate_view_metadata
from .threed import validate_360_manifest

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

    passed=sum(1 for c in checks if c["status"]=="PASS")
    return {
      "contract_version":CONTRACT_VERSION,
      "decision":"PASS" if passed==len(checks) else "FAIL",
      "checks_passed":passed,
      "checks_total":len(checks),
      "checks":checks,
      "invariants":[
        "generation_provider_cannot_approve",
        "missing_policy_blocks",
        "not_applicable_policy_only",
        "calibrated_ai_bound_to_validator_version",
        "correction_exhausts_to_human_review",
        "canonical_multiview_graph",
        "true_360_requires_canonical_3d_or_physical_turntable"
      ]
    }
