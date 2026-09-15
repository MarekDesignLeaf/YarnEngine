from collections import defaultdict
from src.pattern_editor.model import EditorCell,EditorPattern

def canonical_to_editor(pattern, operation_registry):
    cells=[]
    for row in pattern.rows:
        col=1
        for tok in row.sequence:
            op=operation_registry[tok.op]
            produced=max(1,int(op.get("produces_stitches",1)))
            consumed=max(1,int(op.get("consumes_stitches",1)))
            span=produced if produced>0 else consumed
            for _ in range(tok.n):
                cells.append(EditorCell(row=row.row,col=col,operation_id=tok.op,span=span))
                col+=span
    return EditorPattern(pattern.pattern_id,pattern.version,pattern.name,
                         pattern.repeat_width_stitches,pattern.repeat_height_rows,tuple(cells))

def editor_to_canonical_dict(editor):
    rows=defaultdict(list)
    byrow=defaultdict(list)
    for c in editor.cells: byrow[c.row].append(c)
    for r in range(1,editor.height+1):
        cells=sorted(byrow.get(r,[]),key=lambda x:x.col)
        seq=[]
        for c in cells:
            if seq and seq[-1]["op"]==c.operation_id:
                seq[-1]["n"]+=1
            else:
                seq.append({"op":c.operation_id,"n":1})
        rows[r]=seq
    return {
      "pattern_id":editor.pattern_id,
      "version":editor.version,
      "name":editor.name,
      "technique":"knitting",
      "repeat":{"width_stitches":editor.width,"height_rows":editor.height},
      "rows":[{"row":r,"side":"RS" if r%2==1 else "WS","sequence":rows[r]} for r in range(1,editor.height+1)]
    }
