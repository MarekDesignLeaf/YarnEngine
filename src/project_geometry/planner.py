from .model import *
def plan_horizontal(total_stitches,repeat_width,edges=EdgeZone(),partial_mode=PartialRepeatMode.REJECT):
    if total_stitches<=0 or repeat_width<=0: raise ValueError("counts must be > 0")
    usable=total_stitches-edges.left_stitches-edges.right_stitches
    if usable<=0: raise ValueError("edges consume project")
    full,rem=divmod(usable,repeat_width); pl=pr=0
    if rem:
        if partial_mode==PartialRepeatMode.REJECT: raise ValueError("pattern zone not divisible by repeat width")
        if partial_mode==PartialRepeatMode.LEFT: pl=rem
        elif partial_mode==PartialRepeatMode.RIGHT: pr=rem
        elif partial_mode in (PartialRepeatMode.SPLIT,PartialRepeatMode.CENTER):
            pl=rem//2; pr=rem-pl
    h=HorizontalLayout(total_stitches,edges.left_stitches,repeat_width,full,pl,pr,edges.right_stitches,partial_mode.value)
    if h.accounted_stitches!=total_stitches: raise AssertionError("horizontal accounting")
    return h
def plan_vertical(total_rows,repeat_height):
    if total_rows<=0 or repeat_height<=0: raise ValueError("counts must be > 0")
    f,p=divmod(total_rows,repeat_height); v=VerticalLayout(total_rows,repeat_height,f,p)
    if v.accounted_rows!=total_rows: raise AssertionError("vertical accounting")
    return v
