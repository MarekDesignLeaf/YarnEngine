from collections import Counter,defaultdict
CORE_AMIGURUMI_OPS=("SC","SC_INC","SC2TOG","SC_BLO","SC_FLO","SLST","CH")

def coverage(records):
    ops=Counter();yarns=set();crocheters=set();constructions=set();groups=defaultdict(int)
    for r in records:
        yarns.add(r.yarn_id);crocheters.add(r.crocheter_id);constructions.add(r.construction);groups[r.replicate_group_id]+=1
        for op,n in r.operation_counts.items():
            if n:ops[op]+=1
    return {"records":len(records),"distinct_yarns":len(yarns),"distinct_crocheters":len(crocheters),
            "constructions":sorted(constructions),"replicate_groups":dict(groups),
            "operation_record_counts":dict(ops)}

def readiness(records,required_ops=CORE_AMIGURUMI_OPS,min_records_per_op=3,min_replicates=3):
    c=coverage(records);reasons=[]
    for op in required_ops:
        if c["operation_record_counts"].get(op,0)<min_records_per_op:
            reasons.append(f"{op} needs at least {min_records_per_op} measured records")
    if not c["replicate_groups"] or any(n<min_replicates for n in c["replicate_groups"].values()):
        reasons.append(f"each included replicate group needs at least {min_replicates} measurements")
    return {"ready":not reasons,"reasons":reasons,"coverage":c,
      "note":"These are configurable project evidence gates, not universal crochet accuracy standards."}
