
from src.pattern_grammar.grammar import parse_advanced_rows
from src.pattern_import_studio.studio import inspect_bundle

def acquire_structured_text(payload, operations, existing_rows=()):
    """
    Converts explicit abbreviations plus deterministic groups and width-bounded repeats.
    Unsupported or non-tiling control language is returned for manual review.
    """
    repeat=payload.get("repeat") or {}
    parsed=parse_advanced_rows(payload.get("rows",[]),operations,int(repeat.get("width_stitches",0) or 0))
    if not parsed["valid"]:
        return {"stage":"translation_review","valid":False,"translation":parsed,
                "import_report":None,"review_required":True}

    raw={
      "pattern":{
        "pattern_id":payload.get("pattern_id",""),
        "version":payload.get("version","1.0.0"),
        "name":payload.get("name",payload.get("pattern_id","")),
        "repeat":{
          "width_stitches":repeat.get("width_stitches",0),
          "height_rows":repeat.get("height_rows",len(parsed["rows"]))
        },
        "rows":parsed["rows"]
      },
      "metadata":payload.get("metadata",{})
    }
    report=inspect_bundle(raw,operations,existing_rows)
    return {"stage":"import_review" if report["valid"] else "structural_review",
            "valid":report["valid"],"translation":parsed,"import_report":report,
            "review_required":True if report.get("review_required") else False}
