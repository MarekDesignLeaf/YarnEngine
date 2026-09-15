from collections import Counter
from .model import EdgeZone,PartialRepeatMode
from .planner import plan_horizontal,plan_vertical
from .sequence import safe_slice_row

def _add(c,seq,m=1):
    for op,n in seq: c[op]+=n*m

def expand_project(pattern,operations,total_stitches,total_rows,edges=EdgeZone(),partial_mode=PartialRepeatMode.REJECT):
    h=plan_horizontal(total_stitches,pattern.repeat_width_stitches,edges,partial_mode)
    v=plan_vertical(total_rows,pattern.repeat_height_rows)
    total=Counter(); rows=[]
    for idx in range(total_rows):
        r=pattern.rows[idx%pattern.repeat_height_rows]; c=Counter()
        if edges.left_stitches: c[edges.left_operation]+=edges.left_stitches
        if h.partial_left: _add(c,safe_slice_row(r,h.partial_left,operations,False))
        _add(c,[(t.op,t.n) for t in r.sequence],h.full_repeats)
        if h.partial_right: _add(c,safe_slice_row(r,h.partial_right,operations,True))
        if edges.right_stitches: c[edges.right_operation]+=edges.right_stitches
        total.update(c); rows.append(dict(c))
    return {"horizontal_layout":h,"vertical_layout":v,"operation_counts":dict(total),"row_operation_counts":tuple(rows)}
