
from .model import ShapingToken,ShapingRow,ShapedPatternDefinition

def load_shaped_pattern_dict(d):
    rows=[]
    for i,r in enumerate(d["rows"],1):
        rows.append(ShapingRow(
            row=int(r.get("row",i)),
            side=str(r.get("side","NA")).upper(),
            sequence=tuple(ShapingToken(op=str(t["op"]).upper(),n=int(t.get("n",1))) for t in r["sequence"]),
            expected_in=int(r["expected_in"]) if r.get("expected_in") is not None else None,
            expected_out=int(r["expected_out"]) if r.get("expected_out") is not None else None,
        ))
    return ShapedPatternDefinition(
        pattern_id=d["pattern_id"],version=str(d.get("version","1.0.0")),name=d.get("name",d["pattern_id"]),
        initial_stitches=int(d["initial_stitches"]),rows=tuple(rows),construction=str(d.get("construction","flat"))
    )
