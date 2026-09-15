from collections import Counter
from .model import PatternDefinition

def operation_counts_per_repeat(pattern: PatternDefinition) -> dict[str,int]:
    c=Counter()
    for row in pattern.rows:
        for t in row.sequence:
            c[t.op]+=t.n
    return dict(c)

def pattern_signature(pattern: PatternDefinition) -> dict:
    """Stable structural signature useful for deduplication/search."""
    return {
        "repeat_width_stitches":pattern.repeat_width_stitches,
        "repeat_height_rows":pattern.repeat_height_rows,
        "operations":operation_counts_per_repeat(pattern),
        "row_shapes":[[(t.op,t.n) for t in r.sequence] for r in pattern.rows]
    }
