from collections import Counter

CROCHET_OPS={
 "CH","SLST","SC","HDC","DC","TR","DTR","SC2TOG","SC3TOG","HDC2TOG","DC2TOG","DC3TOG",
 "SC_INC","HDC_INC","DC_INC","SC_BLO","SC_FLO","HDC_BLO","DC_BLO","FPDC","BPDC","PUFF3","POPCORN5"
}

def analyse_rounds(payload,operations):
    """Explicit round model for amigurumi shaping.
    Each round supplies canonical operation counts. This avoids pretending that changing stitch-count rounds are fixed repeats."""
    start=int(payload.get("initial_stitches",0)); rounds=payload.get("rounds",[])
    if start<0:return {"valid":False,"issues":[{"code":"INITIAL_STITCHES_INVALID"}]}
    current=start; total=Counter(); trace=[];issues=[]
    for i,r in enumerate(rounds,1):
        counts=r.get("operations",{})
        consumed=produced=0
        for op,n in counts.items():
            if op not in CROCHET_OPS or op not in operations:
                issues.append({"round":i,"code":"UNKNOWN_CROCHET_OPERATION","operation":op});continue
            n=int(n)
            if n<0:issues.append({"round":i,"code":"NEGATIVE_COUNT","operation":op});continue
            consumed+=operations[op]["consumes_stitches"]*n
            produced+=operations[op]["produces_stitches"]*n
            total[op]+=n
        # Round 1 may start from a magic/adjustable ring represented as zero existing stitches.
        if current==0:
            allowed_zero_start=all(operations[op]["consumes_stitches"]==0 for op in counts if op in operations)
            if not allowed_zero_start and consumed!=0:
                issues.append({"round":i,"code":"ROUND_INPUT_MISMATCH","expected":0,"consumed":consumed})
        elif consumed!=current:
            issues.append({"round":i,"code":"ROUND_INPUT_MISMATCH","expected":current,"consumed":consumed})
        if not any(x.get("round")==i for x in issues):
            trace.append({"round":i,"input_stitches":current,"consumed":consumed,"output_stitches":produced,
                          "operations":dict(counts)})
            current=produced
    return {"valid":not issues,"issues":issues,"initial_stitches":start,"final_stitches":current,
            "operation_counts":dict(total),"trace":trace}
