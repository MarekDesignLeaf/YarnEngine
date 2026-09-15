from src.pattern_editor.model import EditorCell,EditorPattern

def paint_cell(editor,row,col,operation_id,operation_registry):
    if operation_id not in operation_registry:
        raise ValueError("unknown operation")
    span=max(1,int(operation_registry[operation_id].get("produces_stitches",1)))
    if row<1 or row>editor.height or col<1 or col+span-1>editor.width:
        raise ValueError("operation does not fit in repeat")
    new=[]
    for c in editor.cells:
        if c.row!=row:
            new.append(c); continue
        a1,a2=c.col,c.col+c.span-1
        b1,b2=col,col+span-1
        if a2<b1 or b2<a1:
            new.append(c)
    new.append(EditorCell(row,col,operation_id,span))
    return EditorPattern(editor.pattern_id,editor.version,editor.name,editor.width,editor.height,
                         tuple(sorted(new,key=lambda x:(x.row,x.col))))

def resize(editor,width,height):
    if width<1 or height<1: raise ValueError("width/height must be >=1")
    kept=tuple(c for c in editor.cells if c.row<=height and c.col+c.span-1<=width)
    return EditorPattern(editor.pattern_id,editor.version,editor.name,width,height,kept)

def fill_empty_with(editor,operation_id,operation_registry):
    span=max(1,int(operation_registry[operation_id].get("produces_stitches",1)))
    if span!=1: raise ValueError("fill operation must span one stitch")
    occ=set()
    for c in editor.cells:
        for x in range(c.col,c.col+c.span): occ.add((c.row,x))
    cells=list(editor.cells)
    for r in range(1,editor.height+1):
        for col in range(1,editor.width+1):
            if (r,col) not in occ:
                cells.append(EditorCell(r,col,operation_id,1))
    return EditorPattern(editor.pattern_id,editor.version,editor.name,editor.width,editor.height,
                         tuple(sorted(cells,key=lambda x:(x.row,x.col))))
