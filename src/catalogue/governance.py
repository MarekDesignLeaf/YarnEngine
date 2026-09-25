"""Catalogue Factory release-governance helpers.

These functions are deliberately deterministic and side-effect free. They encode
release rules that must be independently testable by APVP.
"""
from __future__ import annotations

from hashlib import sha256
import json


def require_exact_asset(expected_sha256:str, actual_sha256:str, *, label:str="asset"):
    if not expected_sha256 or not actual_sha256 or expected_sha256 != actual_sha256:
        raise ValueError(f"{label} exact binary mismatch")
    return True


def validate_page_manifest(pages:list[dict], expected_numbers:list[int]):
    actual=[int(p.get("page_number")) for p in pages]
    if actual != list(expected_numbers):
        raise ValueError("page numbering does not match manifest")
    return True


def physical_fidelity_gate(reference:dict|None, observation:dict|None):
    if not reference:
        return {"decision":"BLOCKED","reason":"physical_reference_missing"}
    if not reference.get("approval_record_id"):
        return {"decision":"BLOCKED","reason":"physical_reference_unapproved"}
    if not observation:
        return {"decision":"BLOCKED","reason":"observation_missing"}
    required=reference.get("required_measurements") or {}
    observed=observation.get("measurements") or {}
    for key,value in required.items():
        if observed.get(key) != value:
            return {"decision":"FAIL","reason":"physical_measurement_mismatch","field":key}
    return {"decision":"PASS","reason":"physical_reference_satisfied"}


def human_override_permitted(*, method:str, zero_tolerance:bool):
    if zero_tolerance and str(method).upper()=="EXACT":
        return False
    return True


def unexpected_text_check(expected:list[str], observed:list[str]):
    e=set(expected or []);o=set(observed or [])
    extra=sorted(o-e)
    missing=sorted(e-o)
    if extra or missing:
        return {"decision":"FAIL","unexpected":extra,"missing":missing}
    return {"decision":"PASS","unexpected":[],"missing":[]}


def require_locale_record(locale:str, records:dict):
    if locale not in records:
        raise ValueError("locale record missing; silent fallback forbidden")
    record=records[locale]
    if not record or not record.get("approved"):
        raise ValueError("locale record is not approved")
    return record


def validate_live_commerce_publish(record:dict|None, history:list[dict]|None, gate:dict|None):
    if not record:return {"decision":"BLOCKED","reason":"commerce_record_missing"}
    if not gate or gate.get("decision")!="APPROVED":
        return {"decision":"BLOCKED","reason":"publication_gate_missing"}
    if not history:
        return {"decision":"BLOCKED","reason":"publication_history_missing"}
    latest=history[-1]
    if latest.get("displayed_value") != record.get("price"):
        return {"decision":"FAIL","reason":"displayed_price_not_auditable"}
    return {"decision":"PASS"}


def canonical_turntable_azimuth(object_rotation_deg:float, mirrored:bool=False):
    if mirrored:
        raise ValueError("mirrored turntable capture violates handedness")
    return (-float(object_rotation_deg)) % 360.0


def require_derived_candidate(source_hash:str, candidate_hash:str, operation:str, validation_required:bool):
    op=str(operation).upper()
    if op not in {"UPSCALE","GENERATIVE_UPSCALE","GLB_OPTIMIZE","GLB_DECIMATE","USDZ_CONVERT"}:
        raise ValueError("unknown derived operation")
    if not source_hash or not candidate_hash or source_hash == candidate_hash:
        raise ValueError("derived output must be a new candidate binary")
    if not validation_required:
        raise ValueError("derived candidate must require revalidation")
    return True


def validate_reproducibility_profile(profile:dict):
    mode=str(profile.get("reproducibility") or "")
    if mode=="BYTE_IDENTICAL":
        for key in ("renderer_version","font_bundle_hash","object_order_policy","release_timestamp"):
            if not profile.get(key):
                raise ValueError("BYTE_IDENTICAL profile missing "+key)
    elif mode=="VISUAL_EQUIVALENCE":
        if profile.get("raster_tolerance") is None or not profile.get("structural_preflight"):
            raise ValueError("VISUAL_EQUIVALENCE profile incomplete")
    else:
        raise ValueError("unknown reproducibility mode")
    return True


def gc_permitted(record:dict):
    if record.get("legal_hold"):
        return False
    if record.get("state") in {"APPROVED","LOCKED","RELEASED"}:
        return False
    return bool(record.get("retention_expired"))


def validate_calibration(record:dict, validator_version:str):
    if not record.get("held_out_dataset"):
        raise ValueError("calibration dataset is not held out")
    if str(record.get("validator_version")) != str(validator_version):
        raise ValueError("calibration does not match validator version")
    if int(record.get("sample_count") or 0) <= 0:
        raise ValueError("calibration sample count missing")
    if not record.get("approved"):
        raise ValueError("calibration is not approved")
    return True


def compliance_claim_allowed(claim:str, approval_records:list[dict]):
    claim=str(claim).upper()
    controlled={"UKCA","CE"}
    if claim not in controlled:
        return True
    for r in approval_records or []:
        if str(r.get("approval_type")).upper()==f"COMPLIANCE_{claim}" and r.get("decision")=="APPROVED":
            return True
    return False


def inventory_diff_reviewed(previous:list[str], current:list[str], reviewed:bool):
    changed=sorted(set(previous or []) ^ set(current or []))
    if changed and not reviewed:
        raise ValueError("rule inventory changed without review")
    return {"changed":changed,"reviewed":bool(reviewed)}


def stable_hash(value:dict):
    raw=json.dumps(value,sort_keys=True,separators=(",",":")).encode("utf-8")
    return sha256(raw).hexdigest()
