from collections import Counter
from src.pattern_grammar.grammar import parse_advanced_row

def _count_ops(tokens):
    c=Counter()
    for t in tokens:
        c[t.op]+=int(t.n)
    return dict(c)

def execute_branch_program(payload,operations):
    initial=int(payload.get("initial_stitches",0))
    if initial<=0:
        return {"valid":False,"issues":[{"code":"INITIAL_STITCHES_REQUIRED"}],"groups":{},"operation_counts":{}}
    groups={"G0":{"stitches":initial,"state":"active","rows_worked":0,"operation_counts":Counter()}}
    total_counts=Counter()
    issues=[];trace=[]
    steps=payload.get("steps",[])
    if len(steps)>5000:
        return {"valid":False,"issues":[{"code":"STEP_LIMIT","message":"maximum 5000 steps"}],"groups":{},"operation_counts":{}}
    for i,s in enumerate(steps,1):
        typ=s.get("type")
        if typ=="split":
            gid=s.get("group");g=groups.get(gid)
            targets=s.get("targets",[])
            if not g or g["state"]!="active":
                issues.append({"step":i,"code":"SPLIT_INVALID_SOURCE","group":gid});continue
            if len(targets)<2 or sum(int(x.get("stitches",0)) for x in targets)!=g["stitches"]:
                issues.append({"step":i,"code":"SPLIT_COUNT_MISMATCH","group":gid});continue
            ids=[x.get("id") for x in targets]
            if any(not x for x in ids) or len(set(ids))!=len(ids) or any(x in groups for x in ids):
                issues.append({"step":i,"code":"SPLIT_TARGET_CONFLICT"});continue
            g["state"]="closed";g["stitches"]=0
            for x in targets:
                groups[x["id"]]={"stitches":int(x["stitches"]),"state":"active","rows_worked":0,
                                 "operation_counts":Counter()}
            trace.append({"step":i,"type":"split","group":gid,"targets":ids})

        elif typ=="hold":
            gid=s.get("group");g=groups.get(gid)
            if not g or g["state"]!="active":
                issues.append({"step":i,"code":"HOLD_INVALID_GROUP","group":gid});continue
            g["state"]="held";trace.append({"step":i,"type":"hold","group":gid})

        elif typ=="activate":
            gid=s.get("group");g=groups.get(gid)
            if not g or g["state"]!="held":
                issues.append({"step":i,"code":"ACTIVATE_INVALID_GROUP","group":gid});continue
            g["state"]="active";trace.append({"step":i,"type":"activate","group":gid})

        elif typ=="row":
            gid=s.get("group");g=groups.get(gid)
            if not g or g["state"]!="active":
                issues.append({"step":i,"code":"ROW_GROUP_NOT_ACTIVE","group":gid});continue
            row_dict,row_issues=parse_advanced_row(str(s.get("instruction","")),operations,g["stitches"])
            if row_issues:
                issues.extend({"step":i,"group":gid,"code":x.get("code"),"message":x.get("message")} for x in row_issues);continue
            seq=row_dict["sequence"]
            consumed=sum(operations[t["op"]]["consumes_stitches"]*t["n"] for t in seq)
            produced=sum(operations[t["op"]]["produces_stitches"]*t["n"] for t in seq)
            if consumed!=g["stitches"]:
                issues.append({"step":i,"code":"ROW_INPUT_MISMATCH","group":gid,"expected":g["stitches"],"consumed":consumed});continue
            g["stitches"]=produced
            g["rows_worked"]+=1
            row_counts={t["op"]:int(t.get("n",1)) for t in seq}
            g["operation_counts"].update(row_counts)
            total_counts.update(row_counts)
            trace.append({"step":i,"type":"row","group":gid,"consumed":consumed,"produced":produced,
                          "instruction":s.get("instruction")})

        elif typ=="join":
            src=s.get("groups",[]);target=s.get("target")
            if len(src)<2 or not target or target in groups:
                issues.append({"step":i,"code":"JOIN_SHAPE_INVALID"});continue
            gs=[]
            for gid in src:
                g=groups.get(gid)
                if not g or g["state"]=="closed":
                    issues.append({"step":i,"code":"JOIN_INVALID_SOURCE","group":gid});gs=[];break
                gs.append(g)
            if not gs:continue
            total=sum(g["stitches"] for g in gs);counts=Counter()
            rows=max((g["rows_worked"] for g in gs),default=0)
            for gid,g in zip(src,gs):
                counts.update(g["operation_counts"]);g["state"]="closed";g["stitches"]=0
            groups[target]={"stitches":total,"state":"active","rows_worked":rows,"operation_counts":counts}
            trace.append({"step":i,"type":"join","groups":src,"target":target,"stitches":total})
        else:
            issues.append({"step":i,"code":"UNKNOWN_STEP_TYPE","type":typ})

    serial={}
    for gid,g in groups.items():
        serial[gid]={**g,"operation_counts":dict(g["operation_counts"])}
    return {"valid":not issues,"issues":issues,"groups":serial,"trace":trace,
            "operation_counts":dict(total_counts),
            "live_stitches":sum(g["stitches"] for g in groups.values() if g["state"]!="closed")}
