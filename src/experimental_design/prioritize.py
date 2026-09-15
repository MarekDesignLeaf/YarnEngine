from dataclasses import dataclass

@dataclass(frozen=True)
class SwatchCandidate:
    candidate_id:str
    pattern_id:str
    yarn_id:str
    knitter_id:str
    operation_counts:dict[str,int]
    wale_spacing_mm:float
    course_spacing_mm:float
    yarn_diameter_mm:float|None=None

@dataclass(frozen=True)
class CandidateScore:
    candidate_id:str
    score:float
    reasons:tuple[str,...]

def rank_candidates(candidates,coverage,model=None):
    """Heuristic design score.

    Rewards:
    * operations with weak record coverage
    * unseen operations
    * new pattern/yarn/knitter groups
    * gauge values near/outside current calibrated domain

    It does not pretend to be an optimal-design theorem; it is a transparent,
    deterministic prioritizer for data collection.
    """
    ranked=[]
    known_ops=set(coverage.operation_record_counts)
    for c in candidates:
        score=0.0; reasons=[]
        used=[op for op,n in c.operation_counts.items() if n>0]
        unseen=[op for op in used if op not in known_ops]
        if unseen:
            score += 50*len(unseen); reasons.append("unseen operations: "+", ".join(sorted(unseen)))
        for op in used:
            rc=coverage.operation_record_counts.get(op,0)
            bonus=max(0,10-rc)
            if bonus:
                score += bonus
        if c.pattern_id not in coverage.pattern_counts:
            score += 20; reasons.append("new pattern")
        if c.yarn_id not in coverage.yarn_counts:
            score += 15; reasons.append("new yarn")
        if c.knitter_id not in coverage.knitter_counts:
            score += 10; reasons.append("new knitter")
        if model is not None:
            for field,val in (("wale_spacing_mm",c.wale_spacing_mm),("course_spacing_mm",c.course_spacing_mm)):
                lo,hi=model.domains[field]
                if val<lo or val>hi:
                    score+=12; reasons.append(f"{field} extends calibrated range")
            lo,hi=model.domains.get("yarn_diameter_mm",[None,None])
            if c.yarn_diameter_mm is not None and lo is not None and (c.yarn_diameter_mm<lo or c.yarn_diameter_mm>hi):
                score+=12; reasons.append("yarn diameter extends calibrated range")
        if not reasons:
            reasons.append("fills existing coverage")
        ranked.append(CandidateScore(c.candidate_id,score,tuple(reasons)))
    return tuple(sorted(ranked,key=lambda x:(-x.score,x.candidate_id)))
