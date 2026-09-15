from dataclasses import dataclass,asdict
from collections import Counter,defaultdict
import hashlib,json

def structural_signature(pattern):
    """Identity independent of pattern name/source metadata.
    Keeps operation order, counts, row sides and repeat geometry."""
    canonical={
      "technique":pattern.get("technique","knitting"),
      "repeat":pattern.get("repeat",{}),
      "rows":[{"side":r.get("side","NA"),
               "sequence":[{"op":x["op"],"n":int(x.get("n",1))} for x in r.get("sequence",[])]}
              for r in pattern.get("rows",[])]
    }
    return hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def classify_family(pattern):
    ops=Counter()
    for row in pattern.get("rows",[]):
        for tok in row.get("sequence",[]):ops[tok["op"]]+=int(tok.get("n",1))
    keys=set(ops)
    if keys <= {"K"}: return "STOCKINETTE_LIKE"
    if keys <= {"K","P"}: return "KNIT_PURL_TEXTURE"
    if keys & {"C1_1R","C1_1L","C1_1RP","C1_1LP","C2_1R","C2_1L","C2_2R","C2_2L","C2_2RP","C2_2LP"}: return "CABLE"
    if keys & {"YO"}: return "EYELET_LACE"
    return "MIXED"

def portfolio_report(items):
    families=Counter();sources=Counter();licenses=Counter();signatures=defaultdict(list);ops=Counter()
    for b in items:
        p=b["pattern"];m=b.get("metadata",{})
        families[m.get("family_id") or classify_family(p)]+=1
        sources[m.get("source_type","unknown")]+=1
        licenses[m.get("license_id") or "UNSPECIFIED"]+=1
        signatures[structural_signature(p)].append(f'{p.get("pattern_id")}@{p.get("version")}')
        for r in p.get("rows",[]):
            for x in r.get("sequence",[]):ops[x["op"]]+=int(x.get("n",1))
    duplicates={k:v for k,v in signatures.items() if len(v)>1}
    return {"total":len(items),"families":dict(families),"source_types":dict(sources),
            "licenses":dict(licenses),"operation_occurrences":dict(ops),
            "structural_duplicate_groups":duplicates,
            "distinct_structures":len(signatures)}

def scale_gate(items,target=100):
    rep=portfolio_report(items);issues=[]
    if rep["total"]<target:issues.append({"code":"TARGET_NOT_REACHED","current":rep["total"],"target":target})
    if "UNSPECIFIED" in rep["licenses"]:issues.append({"code":"LICENSE_REVIEW_REQUIRED","count":rep["licenses"]["UNSPECIFIED"]})
    if rep["structural_duplicate_groups"]:issues.append({"code":"STRUCTURAL_DUPLICATES","groups":len(rep["structural_duplicate_groups"])})
    return {"ready":not issues,"target":target,"issues":issues,"portfolio":rep}
