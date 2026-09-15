from collections import Counter
CORE=("SC","SC_INC","SC2TOG","SC_BLO","SC_FLO","SLST","CH")

def generate_experiment_plan(records, required_ops=CORE, min_records_per_op=3, min_replicates=3,
                             yarn_id=None, crocheter_id=None, hook_mm=None, construction="spiral"):
    """Generate only the missing physical measurements required by the configured evidence gate.
    This is an experimental work plan, not synthetic calibration data."""
    coverage=Counter()
    group_counts=Counter()
    for r in records:
        for op,n in r.operation_counts.items():
            if int(n)>0: coverage[op]+=1
        group_counts[r.replicate_group_id]+=1
    experiments=[]
    seq=1
    for op in required_ops:
        missing=max(0,int(min_records_per_op)-coverage[op])
        if missing:
            group=f"EXP_{op}_{construction.upper()}"
            existing=group_counts[group]
            target=max(missing,max(0,int(min_replicates)-existing))
            for rep in range(existing+1,existing+target+1):
                experiments.append({
                  "experiment_id":f"CAL_{op}_{seq:03d}",
                  "replicate_group_id":group,"operation":op,"replicate":rep,
                  "yarn_id":yarn_id,"crocheter_id":crocheter_id,"hook_mm":hook_mm,
                  "construction":construction,
                  "instruction":{"purpose":f"Measure real yarn consumption for canonical operation {op}",
                    "operation_count_target":None,
                    "note":"Choose a practical sample size large enough for reliable physical length measurement; record the exact executed operation count."},
                  "measure":["gauge_stitches","gauge_rows_or_rounds","gauge_width_mm","gauge_height_mm",
                             "yarn_length_m","yarn_mass_g_optional","yarn_diameter_mm_optional","exact_operation_counts",
                             "evidence_reference"]
                });seq+=1
    return {"complete":not experiments,"experiments":experiments,"count":len(experiments),
            "current_operation_record_counts":dict(coverage),
            "policy":{"required_ops":list(required_ops),"min_records_per_op":int(min_records_per_op),
                      "min_replicates":int(min_replicates)},
            "warning":"Plan minimizes missing evidence against configured gates. It does not claim statistical sufficiency or fabricate measurements."}
