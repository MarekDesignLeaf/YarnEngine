from collections import defaultdict
import math, statistics

def replicate_quality(records, warn_cv=0.10, fail_cv=0.20):
    """Assess repeatability of measured yarn length inside replicate groups.
    CV thresholds are configurable project QC gates, not universal standards."""
    groups=defaultdict(list)
    for r in records: groups[r.replicate_group_id].append(r)
    out=[]; overall="pass"
    for gid,rs in sorted(groups.items()):
        vals=[float(r.yarn_length_m) for r in rs]
        mean=statistics.mean(vals); sd=statistics.stdev(vals) if len(vals)>=2 else None
        cv=(sd/mean) if sd is not None and mean else None
        status="insufficient"
        if len(vals)>=3:
            status="fail" if cv>fail_cv else "warn" if cv>warn_cv else "pass"
        if status=="fail":overall="fail"
        elif status in ("warn","insufficient") and overall=="pass":overall=status
        out.append({"replicate_group_id":gid,"n":len(vals),"mean_yarn_length_m":mean,
                    "sd_yarn_length_m":sd,"cv":cv,"status":status,
                    "record_ids":[r.record_id for r in rs]})
    return {"overall":overall,"groups":out,"thresholds":{"warn_cv":warn_cv,"fail_cv":fail_cv},
            "note":"CV thresholds are configurable project QC gates, not universal crochet standards."}

def measurement_consistency(records, mass_length_tolerance=0.15):
    issues=[]
    for r in records:
        if r.yarn_mass_g is not None and r.tex is not None:
            expected=float(r.yarn_mass_g)*1000.0/float(r.tex)
            rel=abs(expected-r.yarn_length_m)/r.yarn_length_m
            if rel>mass_length_tolerance:
                issues.append({"record_id":r.record_id,"code":"MASS_LENGTH_MISMATCH",
                  "measured_length_m":r.yarn_length_m,"length_from_mass_tex_m":expected,
                  "relative_difference":rel})
    return {"valid":not issues,"issues":issues,"tolerance":mass_length_tolerance,
            "note":"This is an internal consistency check when both mass and tex are supplied."}
