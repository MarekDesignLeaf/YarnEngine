"""Master Visual and multi-view workflow for Catalogue Factory."""
from __future__ import annotations

VIEW_ORDER=("AZ000","AZ045","AZ090","AZ135","AZ180","AZ225","AZ270","AZ315")
VIEW_AZIMUTH={v:int(v[2:]) for v in VIEW_ORDER}

def neighbours(view_token:str):
    if view_token not in VIEW_ORDER: raise ValueError("unknown view token")
    i=VIEW_ORDER.index(view_token)
    return (VIEW_ORDER[(i-1)%len(VIEW_ORDER)],VIEW_ORDER[(i+1)%len(VIEW_ORDER)])

def validate_view_metadata(metadata:dict):
    token=str(metadata.get("view_token") or "").upper()
    if token not in VIEW_ORDER: raise ValueError("PRODUCT_VIEW requires canonical view_token")
    if metadata.get("azimuth_deg") is not None and int(metadata["azimuth_deg"])!=VIEW_AZIMUTH[token]:
        raise ValueError("view_token and azimuth_deg disagree")
    metadata=dict(metadata)
    metadata["view_token"]=token
    metadata["azimuth_deg"]=VIEW_AZIMUTH[token]
    metadata.setdefault("coordinate_convention",{
      "up":"+Y","front":"+Z","product_right":"-X","product_left":"+X",
      "azimuth_direction":"+Z toward -X","look_at":"canonical_product_pivot"})
    return metadata

def identity_checks(master_record:dict, observation:dict):
    """Deterministic comparison of structured observations.

    Image interpretation is deliberately outside this function. AI/CV may
    produce an observation, but only this policy layer decides the checks.
    """
    checks=[]
    def exact(cid, expected, actual):
        status="PASS" if expected==actual else "FAIL"
        checks.append({"id":cid,"status":status,"expected":expected,"actual":actual})
    features=master_record.get("mandatory_features") or {}
    observed=observation.get("features") or {}
    for name,expected in sorted(features.items()):
        exact("FEATURE_COUNT:"+name,expected,observed.get(name))
    for name in sorted(set(observed)-set(features)):
        if observed.get(name) not in (None,0,False,[]):
            checks.append({"id":"FORBIDDEN_EXTRA:"+name,"status":"FAIL","expected":0,"actual":observed.get(name)})
    handed=master_record.get("handed_features") or {}
    obs_handed=observation.get("handed_features") or {}
    for name,expected in sorted(handed.items()):
        exact("HANDEDNESS:"+name,expected,obs_handed.get(name))
    for field in ("silhouette_class","pattern_topology","material_class"):
        if master_record.get(field) is not None:
            exact(field.upper(),master_record.get(field),observation.get(field))
    expected_colours=master_record.get("colours")
    if expected_colours is not None: exact("COLOURS",expected_colours,observation.get("colours"))
    decision="FAIL" if any(x["status"]=="FAIL" for x in checks) else ("PASS" if checks else "BLOCKED")
    return {"decision":decision,"checks":checks}

def consistency_checks(left:dict,right:dict):
    checks=[]
    for field in ("identity_key","feature_signature","material_signature","colour_signature","pattern_signature"):
        a=left.get(field);b=right.get(field)
        if a is None or b is None:
            checks.append({"id":"VIEW_"+field.upper(),"status":"NOT_RUN","left":a,"right":b})
        else:
            checks.append({"id":"VIEW_"+field.upper(),"status":"PASS" if a==b else "FAIL","left":a,"right":b})
    if any(x["status"]=="FAIL" for x in checks): decision="FAIL"
    elif any(x["status"]=="NOT_RUN" for x in checks): decision="BLOCKED"
    else: decision="PASS"
    return {"decision":decision,"checks":checks}
