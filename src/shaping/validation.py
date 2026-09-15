
from dataclasses import dataclass,asdict
from .model import ShapedPatternDefinition

@dataclass(frozen=True)
class ShapingIssue:
    severity: str
    code: str
    message: str
    row: int | None = None

def row_counts(row,operations):
    consumed=produced=0
    unknown=[]
    for token in row.sequence:
        op=operations.get(token.op)
        if op is None:
            unknown.append(token.op);continue
        consumed += int(op["consumes_stitches"])*token.n
        produced += int(op["produces_stitches"])*token.n
    return consumed,produced,unknown

def validate_shaped_pattern(pattern:ShapedPatternDefinition,operations):
    issues=[];trace=[]
    expected_in=pattern.initial_stitches
    expected_rows=list(range(1,len(pattern.rows)+1))
    actual=[r.row for r in pattern.rows]
    if actual!=expected_rows:
        issues.append(ShapingIssue("error","ROW_NUMBER_SEQUENCE",f"rows must be exactly 1..{len(pattern.rows)}"))
    for row in pattern.rows:
        consumed,produced,unknown=row_counts(row,operations)
        for op in unknown:
            issues.append(ShapingIssue("error","UNKNOWN_OPERATION",f"unknown operation {op}",row.row))
        if unknown:
            trace.append({"row":row.row,"expected_in":expected_in,"consumed":consumed,"produced":produced,"delta":produced-consumed})
            continue
        if consumed != expected_in:
            issues.append(ShapingIssue("error","ROW_INPUT_MISMATCH",
                f"row consumes {consumed} stitches but {expected_in} are available from the previous state",row.row))
        if row.expected_in is not None and consumed != row.expected_in:
            issues.append(ShapingIssue("error","DECLARED_INPUT_MISMATCH",
                f"row consumes {consumed}, declared expected_in is {row.expected_in}",row.row))
        if row.expected_out is not None and produced != row.expected_out:
            issues.append(ShapingIssue("error","DECLARED_OUTPUT_MISMATCH",
                f"row produces {produced}, declared expected_out is {row.expected_out}",row.row))
        if produced <= 0 and row.row != len(pattern.rows):
            issues.append(ShapingIssue("error","ZERO_STITCHES_BEFORE_END",
                "row leaves no live stitches for a following row",row.row))
        trace.append({"row":row.row,"expected_in":expected_in,"consumed":consumed,
                      "produced":produced,"delta":produced-consumed})
        expected_in=produced
    return {"valid":not any(x.severity=="error" for x in issues),
            "issues":[asdict(x) for x in issues],"trace":trace,
            "initial_stitches":pattern.initial_stitches,"final_stitches":expected_in}
