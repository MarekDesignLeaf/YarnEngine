"""Catalogue edition state machine v1.5.

This table is transcribed from the generated Section 21 tables bound to
catalogue_factory_state_machines_v1_5.yaml, version 1.5.0,
sha256 17a1f5761facfedeb8c64e77aaee770a69575ae3539ff0322356826350390e49.

Runtime transitions are validated against these rows. Guards remain explicit
application preconditions and are recorded in the audit event.
"""
from __future__ import annotations
from dataclasses import dataclass

VERSION="1.5.0"
SHA256="17a1f5761facfedeb8c64e77aaee770a69575ae3539ff0322356826350390e49"

@dataclass(frozen=True)
class EditionTransition:
    id: str
    source: str
    target: str
    trigger: str
    guard: str
    actor_role: str
    gate: str|None=None

_ROWS:list[EditionTransition]=[]

def _add(tid,source,target,trigger,guard,actor,gate=None):
    _ROWS.append(EditionTransition(tid,source,target,trigger,guard,actor,gate))

_add("E01","DRAFT","INTERIOR_BUILDING","start","manifest_valid","OPERATOR")
_add("E02","DRAFT","INTERIOR_APPROVED","inherit_approved_interior","predecessor_interior_approved_locked_and_current","ORCHESTRATOR","interior_approval")
_add("E03","INTERIOR_BUILDING","INTERIOR_VALIDATING","interior_ready","all_planned_pages_locked","ORCHESTRATOR")
_add("E04","INTERIOR_VALIDATING","INTERIOR_APPROVED","decision_pass","automatic_approval_permitted","DECISION_ENGINE","interior_approval")
_add("E05","INTERIOR_VALIDATING","INTERIOR_HUMAN_REVIEW","decision_pass","human_approval_required","DECISION_ENGINE")
_add("E06","INTERIOR_VALIDATING","INTERIOR_FAILED","decision_fail","","DECISION_ENGINE")
_add("E07","INTERIOR_VALIDATING","INTERIOR_BLOCKED","decision_blocked","","DECISION_ENGINE")
_add("E08","INTERIOR_VALIDATING","INTERIOR_NEEDS_REVIEW","decision_review","","DECISION_ENGINE")
_add("E09","INTERIOR_BLOCKED","INTERIOR_VALIDATING","rerun","blocking_dependency_resolved","ORCHESTRATOR")
_add("E10","INTERIOR_BLOCKED","INTERIOR_HUMAN_REVIEW","escalate_conflict","canonical_conflict_or_nonautomatic_resolution","ORCHESTRATOR")
_add("E11","INTERIOR_NEEDS_REVIEW","INTERIOR_HUMAN_REVIEW","reviewer_assigned","","HUMAN_REVIEWER")
_add("E12","INTERIOR_FAILED","INTERIOR_BUILDING","route_failure","retry_permitted","ORCHESTRATOR")
_add("E13","INTERIOR_FAILED","INTERIOR_HUMAN_REVIEW","route_failure","retry_not_permitted","ORCHESTRATOR")
_add("E14","INTERIOR_HUMAN_REVIEW","INTERIOR_APPROVED","human_approve","human_authority_permits_and_no_exact_ZT_fail","HUMAN_REVIEWER","interior_approval")
_add("E15","INTERIOR_HUMAN_REVIEW","INTERIOR_VALIDATING","adjudication_recorded","evidence_recorded","HUMAN_REVIEWER")
_add("E16","INTERIOR_HUMAN_REVIEW","INTERIOR_FAILED","human_reject","reason_recorded","HUMAN_REVIEWER")
_add("E17","INTERIOR_HUMAN_REVIEW","INTERIOR_BUILDING","human_request_correction","reason_recorded","HUMAN_REVIEWER")
_add("E18","INTERIOR_HUMAN_REVIEW","INTERIOR_CHANGE_REQUESTED","request_change","canonical_conflict_identified","HUMAN_REVIEWER")
_add("E19","INTERIOR_CHANGE_REQUESTED","INTERIOR_BUILDING","cr_approved","new_canonical_version_created","CR_AUTHORITY")
_add("E20","INTERIOR_CHANGE_REQUESTED","INTERIOR_HUMAN_REVIEW","cr_rejected","return_to_prior_review_state","CR_AUTHORITY")
_add("E21","INTERIOR_APPROVED","INTERIOR_LOCKED","lock","pagination_frozen","ORCHESTRATOR")
for s in ("INTERIOR_BUILDING","INTERIOR_VALIDATING","INTERIOR_BLOCKED","INTERIOR_NEEDS_REVIEW","INTERIOR_HUMAN_REVIEW","INTERIOR_FAILED","INTERIOR_CHANGE_REQUESTED","INTERIOR_APPROVED"):
    _add("E22",s,"INTERIOR_BUILDING","upstream_change","","ORCHESTRATOR")
_add("E23","DRAFT","DRAFT","upstream_change","","ORCHESTRATOR")
_add("E24","INTERIOR_LOCKED","COVER_BUILDING","build_cover","spine_inputs_known","ORCHESTRATOR")
_add("E25","INTERIOR_LOCKED","INTERIOR_LOCKED","upstream_change","impact_cover_only","ORCHESTRATOR")
_add("E26","INTERIOR_LOCKED","SUPERSEDED","upstream_change","impact_includes_interior","ORCHESTRATOR")
_add("E27","COVER_BUILDING","COVER_VALIDATING","render_complete","","ORCHESTRATOR")
_add("E28","COVER_VALIDATING","COVER_APPROVED","decision_pass","automatic_approval_permitted","DECISION_ENGINE","cover_approval")
_add("E29","COVER_VALIDATING","COVER_HUMAN_REVIEW","decision_pass","human_approval_required","DECISION_ENGINE")
_add("E30","COVER_VALIDATING","COVER_FAILED","decision_fail","","DECISION_ENGINE")
_add("E31","COVER_VALIDATING","COVER_BLOCKED","decision_blocked","","DECISION_ENGINE")
_add("E32","COVER_VALIDATING","COVER_NEEDS_REVIEW","decision_review","","DECISION_ENGINE")
_add("E33","COVER_BLOCKED","COVER_VALIDATING","rerun","blocking_dependency_resolved","ORCHESTRATOR")
_add("E34","COVER_BLOCKED","COVER_HUMAN_REVIEW","escalate_conflict","canonical_conflict_or_nonautomatic_resolution","ORCHESTRATOR")
_add("E35","COVER_NEEDS_REVIEW","COVER_HUMAN_REVIEW","reviewer_assigned","","HUMAN_REVIEWER")
_add("E36","COVER_FAILED","COVER_BUILDING","route_failure","cover_rebuild_permitted","ORCHESTRATOR")
_add("E37","COVER_FAILED","SUPERSEDED","route_failure","new_version_permitted","ORCHESTRATOR")
_add("E38","COVER_FAILED","COVER_HUMAN_REVIEW","route_failure","escalation_required","ORCHESTRATOR")
_add("E39","COVER_HUMAN_REVIEW","COVER_APPROVED","human_approve","human_authority_permits_and_no_exact_ZT_fail","HUMAN_REVIEWER","cover_approval")
_add("E40","COVER_HUMAN_REVIEW","COVER_VALIDATING","adjudication_recorded","evidence_recorded","HUMAN_REVIEWER")
_add("E41","COVER_HUMAN_REVIEW","COVER_FAILED","human_reject","reason_recorded","HUMAN_REVIEWER")
_add("E42","COVER_HUMAN_REVIEW","COVER_BUILDING","human_request_correction","reason_recorded","HUMAN_REVIEWER")
_add("E43","COVER_HUMAN_REVIEW","COVER_CHANGE_REQUESTED","request_change","canonical_conflict_identified","HUMAN_REVIEWER")
_add("E44","COVER_CHANGE_REQUESTED","COVER_BUILDING","cr_approved","impact_cover_only","CR_AUTHORITY")
_add("E45","COVER_CHANGE_REQUESTED","SUPERSEDED","cr_approved","impact_includes_interior","CR_AUTHORITY")
_add("E46","COVER_CHANGE_REQUESTED","COVER_HUMAN_REVIEW","cr_rejected","return_to_prior_review_state","CR_AUTHORITY")
_cover_working=("COVER_BUILDING","COVER_VALIDATING","COVER_BLOCKED","COVER_NEEDS_REVIEW","COVER_HUMAN_REVIEW","COVER_FAILED","COVER_CHANGE_REQUESTED","COVER_APPROVED")
for s in _cover_working:
    _add("E47",s,"COVER_BUILDING","upstream_change","impact_cover_only","ORCHESTRATOR")
    _add("E48",s,"SUPERSEDED","upstream_change","impact_includes_interior","ORCHESTRATOR")
_add("E49","COVER_APPROVED","COVER_LOCKED","lock","approval_complete","ORCHESTRATOR")
_add("E50","COVER_LOCKED","FINAL_VALIDATING","final_validate","all_dependencies_current","ORCHESTRATOR")
_add("E51","FINAL_VALIDATING","RELEASE_APPROVED","decision_pass","automatic_approval_permitted","DECISION_ENGINE","release_approval")
_add("E52","FINAL_VALIDATING","FINAL_HUMAN_REVIEW","decision_pass","human_approval_required","DECISION_ENGINE")
_add("E53","FINAL_VALIDATING","FINAL_FAILED","decision_fail","","DECISION_ENGINE")
_add("E54","FINAL_VALIDATING","FINAL_BLOCKED","decision_blocked","","DECISION_ENGINE")
_add("E55","FINAL_VALIDATING","FINAL_NEEDS_REVIEW","decision_review","","DECISION_ENGINE")
_add("E56","FINAL_BLOCKED","FINAL_VALIDATING","rerun","blocking_dependency_resolved","ORCHESTRATOR")
_add("E57","FINAL_BLOCKED","FINAL_HUMAN_REVIEW","escalate_conflict","canonical_conflict_or_nonautomatic_resolution","ORCHESTRATOR")
_add("E58","FINAL_NEEDS_REVIEW","FINAL_HUMAN_REVIEW","reviewer_assigned","","HUMAN_REVIEWER")
_add("E59","FINAL_FAILED","SUPERSEDED","route_failure","new_version_permitted","ORCHESTRATOR")
_add("E60","FINAL_FAILED","FINAL_HUMAN_REVIEW","route_failure","new_version_not_permitted","ORCHESTRATOR")
_add("E61","FINAL_HUMAN_REVIEW","RELEASE_APPROVED","human_approve","release_authority_permits","RELEASE_AUTHORITY","release_approval")
_add("E62","FINAL_HUMAN_REVIEW","FINAL_VALIDATING","adjudication_recorded","evidence_recorded","HUMAN_REVIEWER")
_add("E63","FINAL_HUMAN_REVIEW","FINAL_FAILED","human_reject","reason_recorded","HUMAN_REVIEWER")
_add("E64","FINAL_HUMAN_REVIEW","FINAL_CHANGE_REQUESTED","request_change","canonical_conflict_identified","HUMAN_REVIEWER")
_add("E65","FINAL_CHANGE_REQUESTED","SUPERSEDED","cr_approved","new_canonical_version_created","CR_AUTHORITY")
_add("E66","FINAL_CHANGE_REQUESTED","FINAL_HUMAN_REVIEW","cr_rejected","return_to_prior_review_state","CR_AUTHORITY")
_add("E67","RELEASE_APPROVED","EXPORTING","export_start","export_profile_valid","ORCHESTRATOR")
_add("E68","EXPORTING","EXPORTED","export_verified","reproducibility_and_preflight_pass","ORCHESTRATOR","export_verification")
_add("E69","EXPORTING","EXPORT_FAILED","export_failed","","ORCHESTRATOR")
_add("E70","EXPORT_FAILED","EXPORTING","route_failure","retry_permitted","ORCHESTRATOR")
_add("E71","EXPORT_FAILED","EXPORT_HUMAN_REVIEW","route_failure","retry_not_permitted","ORCHESTRATOR")
_add("E72","EXPORT_HUMAN_REVIEW","EXPORTING","retry_export_after_review","export_issue_resolved_without_content_change","HUMAN_REVIEWER")
_add("E73","EXPORT_HUMAN_REVIEW","SUPERSEDED","content_change_required","new_edition_version_required","HUMAN_REVIEWER")
_add("E74","EXPORTED","RELEASED","publish","all_dependencies_current_and_release_record_written","RELEASE_AUTHORITY")
_add("E75","RELEASED","WITHDRAWN","withdraw","reason_recorded","LEGAL_AUTHORITY")
for s in ("COVER_LOCKED","FINAL_VALIDATING","FINAL_BLOCKED","FINAL_NEEDS_REVIEW","FINAL_HUMAN_REVIEW","FINAL_FAILED","FINAL_CHANGE_REQUESTED","RELEASE_APPROVED","EXPORTING","EXPORT_FAILED","EXPORT_HUMAN_REVIEW","EXPORTED"):
    _add("E76",s,"SUPERSEDED","upstream_change","","ORCHESTRATOR")
_DISCARDABLE=(
 "DRAFT","INTERIOR_BUILDING","INTERIOR_VALIDATING","INTERIOR_BLOCKED","INTERIOR_NEEDS_REVIEW",
 "INTERIOR_HUMAN_REVIEW","INTERIOR_FAILED","INTERIOR_CHANGE_REQUESTED","INTERIOR_APPROVED","INTERIOR_LOCKED",
 "COVER_BUILDING","COVER_VALIDATING","COVER_BLOCKED","COVER_NEEDS_REVIEW","COVER_HUMAN_REVIEW",
 "COVER_FAILED","COVER_CHANGE_REQUESTED","COVER_APPROVED","COVER_LOCKED","FINAL_VALIDATING","FINAL_BLOCKED",
 "FINAL_NEEDS_REVIEW","FINAL_HUMAN_REVIEW","FINAL_FAILED","FINAL_CHANGE_REQUESTED","RELEASE_APPROVED",
 "EXPORTING","EXPORT_FAILED","EXPORT_HUMAN_REVIEW","EXPORTED"
)
for s in _DISCARDABLE:
    _add("E77",s,"DISCARDED","discard","edition_abandoned","RELEASE_AUTHORITY")

TRANSITIONS=tuple(_ROWS)
TERMINAL_STATES=frozenset({"WITHDRAWN","SUPERSEDED","DISCARDED"})
TRANSITIONS_BY_PAIR:dict[tuple[str,str],tuple[EditionTransition,...]]={}
for row in TRANSITIONS:
    key=(row.source,row.target)
    TRANSITIONS_BY_PAIR[key]=(*TRANSITIONS_BY_PAIR.get(key,()),row)

def transition_candidates(source:str,target:str):
    return TRANSITIONS_BY_PAIR.get((source,target),())

def allowed_targets(source:str):
    return {t.target for t in TRANSITIONS if t.source==source}

def required_actor_roles(source:str,target:str):
    return {t.actor_role for t in transition_candidates(source,target)}

def select_transition(source:str,target:str,actor_role:str,trigger:str|None=None):
    candidates=[t for t in transition_candidates(source,target) if t.actor_role==actor_role]
    if trigger:
        candidates=[t for t in candidates if t.trigger==trigger]
    if not candidates:
        raise ValueError(f"invalid or unauthorised catalogue transition {source} -> {target} for {actor_role}")
    if len(candidates)>1 and not trigger:
        raise ValueError(f"transition {source} -> {target} is ambiguous; trigger is required")
    return candidates[0]
