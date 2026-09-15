from src.pattern_import_studio.studio import inspect_bundle
from .pipeline import structural_signature,portfolio_report

def inspect_scaling_batch(items,operations,existing_rows=()):
    reports=[];seen={}
    for i,item in enumerate(items):
        r=inspect_bundle(item,operations,existing_rows)
        if r.get("bundle"):
            sig=structural_signature(r["bundle"]["pattern"])
            r["structural_signature"]=sig
            if sig in seen:
                r["structural_duplicate"]={"batch_index":seen[sig]}
                r["review_required"]=True
                r["issues"].append({"severity":"warning","code":"STRUCTURAL_DUPLICATE",
                  "message":"Pattern structure duplicates another item in this batch","row":None})
            else:seen[sig]=i
        reports.append(r)
    valid_bundles=[r["bundle"] for r in reports if r.get("valid") and r.get("bundle")]
    return {"total":len(reports),"valid":sum(bool(r.get("valid")) for r in reports),
            "review_required":sum(bool(r.get("review_required")) for r in reports),
            "reports":reports,"portfolio":portfolio_report(valid_bundles)}
