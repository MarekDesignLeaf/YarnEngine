from dataclasses import dataclass
from collections import defaultdict
from math import sqrt

@dataclass(frozen=True)
class ReplicateSummary:
    replicate_group_id:str
    n:int
    mean_length_m:float
    sample_sd_m:float
    cv_percent:float | None
    min_m:float
    max_m:float

def summarize_replicates(records):
    groups=defaultdict(list)
    for r in records:
        groups[r.replicate_group_id].append(r.yarn_length_m)
    out=[]
    for gid,vals in sorted(groups.items()):
        n=len(vals); mean=sum(vals)/n
        sd=sqrt(sum((x-mean)**2 for x in vals)/(n-1)) if n>1 else 0.0
        cv=(sd/mean*100) if mean else None
        out.append(ReplicateSummary(gid,n,mean,sd,cv,min(vals),max(vals)))
    return tuple(out)

def flag_unstable_replicates(records, cv_threshold_percent=5.0, min_replicates=3):
    flags=[]
    for s in summarize_replicates(records):
        if s.n < min_replicates:
            flags.append((s.replicate_group_id,"insufficient_replicates",s.n))
        elif s.cv_percent is not None and s.cv_percent > cv_threshold_percent:
            flags.append((s.replicate_group_id,"high_cv_percent",s.cv_percent))
    return tuple(flags)
