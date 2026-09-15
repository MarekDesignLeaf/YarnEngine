from dataclasses import dataclass

@dataclass(frozen=True)
class EditorIssue:
    code:str
    message:str
    row:int|None=None
    col:int|None=None

def validate_editor_grid(editor,operation_registry):
    issues=[]
    occupied={}
    for c in editor.cells:
        if c.row>editor.height or c.col>editor.width:
            issues.append(EditorIssue("OUT_OF_BOUNDS","cell starts outside repeat",c.row,c.col))
            continue
        if c.operation_id not in operation_registry:
            issues.append(EditorIssue("UNKNOWN_OPERATION",c.operation_id,c.row,c.col))
            continue
        op=operation_registry[c.operation_id]
        produced=max(1,int(op.get("produces_stitches",1)))
        expected=produced
        if c.span!=expected:
            issues.append(EditorIssue("SPAN_MISMATCH",f"{c.operation_id} requires span {expected}",c.row,c.col))
        if c.col+c.span-1>editor.width:
            issues.append(EditorIssue("SPAN_OVERFLOW","operation crosses repeat boundary",c.row,c.col))
        for x in range(c.col,min(editor.width,c.col+c.span-1)+1):
            key=(c.row,x)
            if key in occupied:
                issues.append(EditorIssue("OVERLAP",f"overlaps {occupied[key]}",c.row,x))
            occupied[key]=c.operation_id
    for r in range(1,editor.height+1):
        missing=[c for c in range(1,editor.width+1) if (r,c) not in occupied]
        if missing:
            issues.append(EditorIssue("ROW_GAPS",f"row has unfilled columns: {missing}",r,missing[0]))
    return tuple(issues)
