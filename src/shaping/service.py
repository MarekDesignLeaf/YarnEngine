
from src.pattern_grammar.grammar import parse_advanced_row
from .loader import load_shaped_pattern_dict
from .validation import validate_shaped_pattern

def translate_shaping(payload,operations):
    initial=int(payload.get("initial_stitches",0) or 0)
    if initial<=0:
        return {"valid":False,"stage":"translation_review",
                "issues":[{"severity":"error","code":"INITIAL_STITCHES_REQUIRED",
                           "message":"initial_stitches must be > 0","row":None}],"pattern":None,"trace":[]}
    current=initial;rows=[];translation_issues=[]
    for i,r in enumerate(payload.get("rows",[]),1):
        rownum=int(r.get("row",i)) if isinstance(r,dict) else i
        side=str(r.get("side","NA")).upper() if isinstance(r,dict) else "NA"
        text=r.get("instruction","") if isinstance(r,dict) else str(r)
        parsed,issues=parse_advanced_row(text,operations,current,rownum,side)
        translation_issues.extend(issues)
        rows.append({**parsed,"expected_in":current})
        # Advance only when fully parsable.
        if not issues:
            consumed=sum(int(operations[t["op"]]["consumes_stitches"])*t["n"] for t in parsed["sequence"])
            produced=sum(int(operations[t["op"]]["produces_stitches"])*t["n"] for t in parsed["sequence"])
            if consumed==current:
                rows[-1]["expected_out"]=produced
                current=produced
    if translation_issues:
        return {"valid":False,"stage":"translation_review","issues":translation_issues,"pattern":None,"trace":[]}
    raw={"pattern_id":payload.get("pattern_id",""),"version":payload.get("version","1.0.0"),
         "name":payload.get("name",payload.get("pattern_id","")),"initial_stitches":initial,
         "construction":payload.get("construction","flat"),"rows":rows}
    try:
        pat=load_shaped_pattern_dict(raw)
    except Exception as e:
        return {"valid":False,"stage":"structural_review",
                "issues":[{"severity":"error","code":"SHAPING_MODEL_ERROR","message":str(e),"row":None}],
                "pattern":raw,"trace":[]}
    report=validate_shaped_pattern(pat,operations)
    return {"valid":report["valid"],"stage":"shaping_valid" if report["valid"] else "structural_review",
            "issues":report["issues"],"pattern":raw,"trace":report["trace"],
            "initial_stitches":report["initial_stitches"],"final_stitches":report["final_stitches"]}
