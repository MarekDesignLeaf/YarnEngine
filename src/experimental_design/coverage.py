from dataclasses import dataclass
from collections import Counter,defaultdict

@dataclass(frozen=True)
class CoverageReport:
    n_records:int
    distinct_patterns:int
    distinct_yarns:int
    distinct_knitters:int
    operation_record_counts:dict[str,int]
    operation_occurrence_counts:dict[str,int]
    undercovered_operations:tuple[str,...]
    pattern_counts:dict[str,int]
    yarn_counts:dict[str,int]
    knitter_counts:dict[str,int]

def analyse_coverage(records,min_records_per_operation=5):
    op_records=Counter(); op_occ=Counter(); p=Counter(); y=Counter(); k=Counter()
    for r in records:
        p[r.pattern_id]+=1; y[r.yarn_id]+=1; k[r.knitter_id]+=1
        for op,n in r.operation_counts.items():
            if n>0:
                op_records[op]+=1
                op_occ[op]+=n
    under=tuple(sorted(op for op,c in op_records.items() if c<min_records_per_operation))
    return CoverageReport(len(records),len(p),len(y),len(k),dict(op_records),dict(op_occ),under,dict(p),dict(y),dict(k))
