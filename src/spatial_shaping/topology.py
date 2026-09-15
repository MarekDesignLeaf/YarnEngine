
from dataclasses import dataclass,asdict
from src.shaping.loader import load_shaped_pattern_dict
from src.shaping.validation import validate_shaped_pattern

@dataclass(frozen=True)
class SpatialEvent:
    row:int
    op:str
    input_start:int
    input_end:int
    output_start:int
    output_end:int
    consumed:int
    produced:int
    delta:int
    normalized_input_center:float | None
    normalized_output_center:float | None

def _center(start,end,total):
    if total<=0 or end<start:
        return None
    c=(start+end)/2.0
    return c/total

def build_spatial_topology(pattern,operations):
    validation=validate_shaped_pattern(pattern,operations)
    if not validation["valid"]:
        return {"valid":False,"issues":validation["issues"],"rows":[]}

    rows=[]
    current_width=pattern.initial_stitches
    for row in pattern.rows:
        input_cursor=1
        output_cursor=1
        events=[]
        for token in row.sequence:
            op=operations[token.op]
            c=int(op["consumes_stitches"])
            p=int(op["produces_stitches"])
            for _ in range(token.n):
                i0=input_cursor
                i1=input_cursor+c-1 if c>0 else input_cursor-1
                o0=output_cursor
                o1=output_cursor+p-1 if p>0 else output_cursor-1
                events.append(SpatialEvent(
                    row=row.row,op=token.op,
                    input_start=i0,input_end=i1,
                    output_start=o0,output_end=o1,
                    consumed=c,produced=p,delta=p-c,
                    normalized_input_center=_center(i0,i1,current_width) if c>0 else None,
                    normalized_output_center=None,
                ))
                input_cursor += c
                output_cursor += p
        output_width=output_cursor-1
        # normalized output positions need final row width
        fixed=[]
        for e in events:
            d=asdict(e)
            d["normalized_output_center"]=_center(e.output_start,e.output_end,output_width) if e.produced>0 else None
            fixed.append(d)
        shaping=[e for e in fixed if e["delta"]!=0]
        rows.append({
            "row":row.row,
            "side":row.side,
            "input_stitches":current_width,
            "output_stitches":output_width,
            "delta":output_width-current_width,
            "events":fixed,
            "shaping_events":shaping,
        })
        current_width=output_width
    return {
        "valid":True,
        "issues":[],
        "initial_stitches":pattern.initial_stitches,
        "final_stitches":current_width,
        "rows":rows,
    }

def topology_profile(topology):
    if not topology.get("valid"):
        return {"valid":False,"rows":[]}
    rows=[]
    for r in topology["rows"]:
        inc=[e["normalized_output_center"] for e in r["shaping_events"] if e["delta"]>0 and e["normalized_output_center"] is not None]
        dec=[e["normalized_input_center"] for e in r["shaping_events"] if e["delta"]<0 and e["normalized_input_center"] is not None]
        rows.append({
            "row":r["row"],
            "input_stitches":r["input_stitches"],
            "output_stitches":r["output_stitches"],
            "net_delta":r["delta"],
            "increase_positions":inc,
            "decrease_positions":dec,
        })
    return {"valid":True,"rows":rows}

def approximate_2d_outline(topology, stitch_width_mm:float=1.0, row_height_mm:float=1.0):
    """
    Geometric preview only. Uses stitch/row dimensions supplied by caller.
    Does not claim to reconstruct physical 3D fabric deformation.
    """
    if stitch_width_mm<=0 or row_height_mm<=0:
        raise ValueError("stitch_width_mm and row_height_mm must be > 0")
    if not topology.get("valid"):
        return {"valid":False,"points_left":[],"points_right":[]}
    left=[];right=[]
    for idx,r in enumerate(topology["rows"],1):
        width_mm=r["output_stitches"]*stitch_width_mm
        y=idx*row_height_mm
        left.append({"x_mm":-width_mm/2.0,"y_mm":y,"row":r["row"]})
        right.append({"x_mm":width_mm/2.0,"y_mm":y,"row":r["row"]})
    return {"valid":True,"points_left":left,"points_right":right,
            "basis":"stitch-count geometric preview, not physical surface reconstruction"}
