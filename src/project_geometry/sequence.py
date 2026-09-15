def expand_atomic_units(row,operations):
    units=[]
    for t in row.sequence:
        op=operations[t.op]; c=int(op["consumes_stitches"])
        if c==0:
            units += [("ZERO",t.op)]*t.n
        else:
            for _ in range(t.n):
                units.append(("HEAD",t.op,c))
                for _ in range(c-1): units.append(("CONT",t.op,c))
    return units

def safe_slice_row(row,take_stitches,operations,from_right=False):
    if take_stitches==0: return []
    units=expand_atomic_units(row,operations)
    # zero-consumption operators mean stitch-position slicing is ambiguous
    if any(u[0]=="ZERO" for u in units): raise ValueError("zero-consumption operation requires explicit edge fragment")
    if take_stitches<0 or take_stitches>len(units): raise ValueError("bad slice")
    chosen=units[-take_stitches:] if from_right else units[:take_stitches]
    if chosen and chosen[0][0]=="CONT": raise ValueError("partial begins inside atomic operation")
    if chosen and chosen[-1][0]=="HEAD" and chosen[-1][2]>1: raise ValueError("partial ends inside atomic operation")
    out=[]; i=0
    while i<len(chosen):
        kind,op,c=chosen[i]
        if kind!="HEAD": raise ValueError("unsafe partial boundary")
        if i+c>len(chosen) or any(chosen[j][1]!=op for j in range(i,i+c)): raise ValueError("atomic operation incomplete")
        out.append((op,1)); i+=c
    comp=[]
    for op,n in out:
        if comp and comp[-1][0]==op: comp[-1]=(op,comp[-1][1]+n)
        else: comp.append((op,n))
    return comp
