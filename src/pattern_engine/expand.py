from dataclasses import dataclass
from collections import Counter
from .model import PatternDefinition

@dataclass(frozen=True)
class ExpandedPattern:
    width_stitches: int
    height_rows: int
    full_repeats_x: int
    full_repeats_y: int
    operation_counts: dict[str,int]
    row_operation_counts: tuple[dict[str,int], ...]
    warnings: tuple[str,...]

def _row_counts(row, repeats_x: int) -> dict[str,int]:
    c=Counter()
    for t in row.sequence:
        c[t.op] += t.n*repeats_x
    return dict(c)

def expand_full_repeats(pattern: PatternDefinition, width_stitches: int, height_rows: int) -> ExpandedPattern:
    if width_stitches <= 0 or height_rows <= 0:
        raise ValueError("project stitch/row counts must be > 0")
    if width_stitches % pattern.repeat_width_stitches != 0:
        raise ValueError(
            f"width {width_stitches} is not divisible by repeat width {pattern.repeat_width_stitches}; "
            "partial-repeat and edge handling is intentionally deferred"
        )
    if height_rows % pattern.repeat_height_rows != 0:
        raise ValueError(
            f"height {height_rows} is not divisible by repeat height {pattern.repeat_height_rows}; "
            "partial vertical repeats are intentionally deferred"
        )
    rx=width_stitches//pattern.repeat_width_stitches
    ry=height_rows//pattern.repeat_height_rows
    total=Counter()
    row_counts=[]
    for _ in range(ry):
        for row in pattern.rows:
            rc=_row_counts(row,rx)
            row_counts.append(rc)
            total.update(rc)
    return ExpandedPattern(
        width_stitches=width_stitches,height_rows=height_rows,
        full_repeats_x=rx,full_repeats_y=ry,
        operation_counts=dict(total),
        row_operation_counts=tuple(row_counts),
        warnings=()
    )
