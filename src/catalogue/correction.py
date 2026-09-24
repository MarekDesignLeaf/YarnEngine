"""Fail-closed correction planning.

Every correction creates a new candidate. Existing candidates and approved
binaries remain immutable evidence.
"""
from __future__ import annotations
from dataclasses import dataclass

ORDER=("LOCAL_EDIT","CONSTRAINED_REGENERATION","FULL_REGENERATION","HUMAN_REVIEW")

@dataclass(frozen=True)
class CorrectionPlan:
    action: str
    reason: str
    attempt: int
    parent_asset_id: int


def choose_correction(parent_asset_id:int, failed_checks:list[dict], history:list[dict],
                      local_edit_allowed:bool=True, max_regenerations:int=2) -> CorrectionPlan:
    failures=[x for x in failed_checks if x.get("status")=="FAIL"]
    if not failures:
        return CorrectionPlan("HUMAN_REVIEW","no concrete FAIL available for automatic correction",len(history)+1,parent_asset_id)
    used=[h.get("action") for h in history]
    local_only=all(str(x.get("scope") or "").upper() in {"LOCAL","REGION","TEXT"} for x in failures)
    if local_edit_allowed and local_only and "LOCAL_EDIT" not in used:
        return CorrectionPlan("LOCAL_EDIT","all failures are locally addressable",len(history)+1,parent_asset_id)
    regen_count=sum(1 for x in used if x in {"CONSTRAINED_REGENERATION","FULL_REGENERATION"})
    if "CONSTRAINED_REGENERATION" not in used and regen_count<max_regenerations:
        return CorrectionPlan("CONSTRAINED_REGENERATION","identity-preserving regeneration required",len(history)+1,parent_asset_id)
    if "FULL_REGENERATION" not in used and regen_count<max_regenerations:
        return CorrectionPlan("FULL_REGENERATION","constrained correction exhausted",len(history)+1,parent_asset_id)
    return CorrectionPlan("HUMAN_REVIEW","automatic correction budget exhausted",len(history)+1,parent_asset_id)
