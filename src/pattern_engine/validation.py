from dataclasses import dataclass
from .model import PatternDefinition

@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    row: int | None = None

@dataclass(frozen=True)
class ValidationReport:
    valid: bool
    issues: tuple[ValidationIssue, ...]

def validate_pattern(pattern: PatternDefinition, operations: dict[str,dict]) -> ValidationReport:
    issues=[]
    seen=set()
    expected=set(range(1,pattern.repeat_height_rows+1))
    actual={r.row for r in pattern.rows}
    if actual != expected:
        issues.append(ValidationIssue("error","ROW_NUMBER_SEQUENCE",
            f"row numbers must be exactly 1..{pattern.repeat_height_rows}"))
    for row in pattern.rows:
        if row.row in seen:
            issues.append(ValidationIssue("error","DUPLICATE_ROW",f"duplicate row {row.row}",row.row))
        seen.add(row.row)
        consumed=produced=0
        for token in row.sequence:
            op=operations.get(token.op)
            if op is None:
                issues.append(ValidationIssue("error","UNKNOWN_OPERATION",
                    f"unknown operation {token.op}",row.row))
                continue
            consumed += int(op["consumes_stitches"])*token.n
            produced += int(op["produces_stitches"])*token.n
        if consumed != pattern.repeat_width_stitches:
            issues.append(ValidationIssue("error","CONSUMED_WIDTH_MISMATCH",
                f"consumes {consumed}, expected {pattern.repeat_width_stitches}",row.row))
        if produced != pattern.repeat_width_stitches:
            issues.append(ValidationIssue("error","PRODUCED_WIDTH_MISMATCH",
                f"produces {produced}, expected {pattern.repeat_width_stitches}",row.row))
    return ValidationReport(
        valid=not any(i.severity=="error" for i in issues),
        issues=tuple(issues)
    )
