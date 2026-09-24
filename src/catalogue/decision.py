"""Catalogue Factory validation Decision Engine."""
from __future__ import annotations

STATUSES={"PASS","FAIL","NOT_RUN","UNAVAILABLE","UNCERTAIN","NOT_APPLICABLE","ERROR"}

def decide(policy:dict|None, results:list[dict]) -> dict:
    if not policy or not policy.get("policy_id") or not policy.get("policy_version"):
        return {"decision":"BLOCKED","reason":"missing_or_invalid_policy"}
    required=list(policy.get("required_check_ids") or [])
    if not required:
        return {"decision":"BLOCKED","reason":"required_check_ids_empty"}
    by={}
    duplicates=set()
    for r in results:
        cid=r.get("check_id") or r.get("id")
        if not cid: continue
        if cid in by:duplicates.add(cid)
        by[cid]=r
    if duplicates:
        return {"decision":"BLOCKED","reason":"duplicate_check_results","checks":sorted(duplicates)}
    concrete=[]
    for cid in required:
        r=by.get(cid)
        if r is None:return {"decision":"BLOCKED","reason":"required_check_missing","check_id":cid}
        status=str(r.get("status") or "").upper()
        if status not in STATUSES:return {"decision":"BLOCKED","reason":"invalid_status","check_id":cid}
        concrete.append((cid,status,r))
    fails=[cid for cid,s,_ in concrete if s=="FAIL"]
    if fails:return {"decision":"FAIL","reason":"mandatory_fail","checks":fails}
    errors=[cid for cid,s,_ in concrete if s=="ERROR"]
    if errors:return {"decision":"BLOCKED","reason":"validator_error","checks":errors}
    unavailable=[cid for cid,s,_ in concrete if s in {"NOT_RUN","UNAVAILABLE"}]
    if unavailable:return {"decision":"BLOCKED","reason":"mandatory_check_unavailable","checks":unavailable}
    uncertain=[cid for cid,s,_ in concrete if s=="UNCERTAIN"]
    if uncertain:return {"decision":"NEEDS_REVIEW","reason":"uncertain","checks":uncertain}
    for cid,status,r in concrete:
        if status=="NOT_APPLICABLE":
            if r.get("assigned_by")!="POLICY":
                return {"decision":"BLOCKED","reason":"not_applicable_not_policy_assigned","check_id":cid}
            continue
        if status=="PASS":
            if not r.get("evidence"):
                return {"decision":"BLOCKED","reason":"pass_missing_evidence","check_id":cid}
            method=str(r.get("method") or "").upper()
            if method in {"CALIBRATED_CV","CALIBRATED_AI","CV","AI"}:
                if not r.get("calibration_id") or r.get("calibration_validator_version")!=r.get("validator_version"):
                    return {"decision":"BLOCKED","reason":"calibration_missing_or_stale","check_id":cid}
    disagreement=policy.get("disagreement_check_ids") or []
    if any((by.get(cid) or {}).get("disagreement") for cid in disagreement):
        return {"decision":"NEEDS_REVIEW","reason":"validator_disagreement"}
    return {"decision":"PASS","reason":"all_required_checks_satisfied"}
