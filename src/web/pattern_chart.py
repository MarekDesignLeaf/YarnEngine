from dataclasses import dataclass, asdict
import json
from pathlib import Path

# Application-native symbols. These are deliberately not presented as a copy of
# any external chart-symbol standard. The operation ID remains the canonical semantic value.
SYMBOLS = {
    "K": "│",
    "P": "●",
    "YO": "○",
    "K2TOG": "╲",
    "P2TOG": "╲p",
    "SSK": "╱",
    "SSP": "╱p",
    "KFB": "V",
    "M1L": "+L",
    "M1R": "+R",
    "SL1_WYIB": "S",
    "SL1_WYIF": "S",
    "K3TOG": "╲3",
    "P3TOG": "╲p3",
    "S2KP2": "⇓",
    "K_TBL": "│×",
    "P_TBL": "●×",
    "BO": "BO",
    "CO": "CO",
    "C1_1R": "C→",
    "C1_1L": "C←",
    "C1_1RP": "C→p",
    "C1_1LP": "C←p",
    "C2_1R": "C→",
    "C2_1L": "C←",
    "C2_2R": "C→",
    "C2_2L": "C←",
    "C2_2RP": "C→p",
    "C2_2LP": "C←p",
    "BOBBLE": "✦",
}

@dataclass(frozen=True)
class ChartCell:
    op: str
    name: str
    family: str
    symbol: str
    span: int
    count: int
    start_column: int
    end_column: int


def load_operation_map(root: Path):
    rows = json.loads((root / "data/stitches/operations.seed.json").read_text(encoding="utf-8"))
    return {x["operation_id"]: x for x in rows}


def build_pattern_chart(pattern, operation_map):
    rows=[]
    legend={}
    width=pattern.repeat_width_stitches

    # Display highest row first, matching conventional chart presentation while
    # preserving the row's stored operation sequence. Direction is explicit metadata.
    for row in reversed(pattern.rows):
        col=1
        cells=[]
        for token in row.sequence:
            op=operation_map[token.op]
            produced=int(op.get("produces_stitches", 0))
            consumed=int(op.get("consumes_stitches", 0))
            # Chart columns describe fabric positions after the row is formed.
            # If an operation has zero produced stitches (e.g. bind off), fall back
            # to consumed width so it remains visible rather than disappearing.
            unit_span=max(1, produced if produced > 0 else consumed)
            for _ in range(token.n):
                span=unit_span
                cell=ChartCell(
                    op=token.op,
                    name=op["name"],
                    family=op.get("family", "unknown"),
                    symbol=SYMBOLS.get(token.op, token.op),
                    span=span,
                    count=1,
                    start_column=col,
                    end_column=col+span-1,
                )
                cells.append(asdict(cell))
                col += span
                legend[token.op]={
                    "op":token.op,
                    "name":op["name"],
                    "family":op.get("family","unknown"),
                    "symbol":SYMBOLS.get(token.op,token.op),
                }
        rows.append({
            "row":row.row,
            "side":row.side,
            "direction":"right_to_left" if row.side=="RS" else "left_to_right" if row.side=="WS" else "unspecified",
            "cells":cells,
            "produced_columns":col-1,
        })

    warnings=[]
    bad=[r for r in rows if r["produced_columns"] != width]
    if bad:
        warnings.append("One or more rows do not render to the declared repeat width using produced-stitch geometry.")

    return {
        "pattern_id":pattern.pattern_id,
        "version":pattern.version,
        "name":pattern.name,
        "repeat_width":width,
        "repeat_height":pattern.repeat_height_rows,
        "rows":rows,
        "legend":[legend[k] for k in sorted(legend)],
        "symbol_system":"YCE application-native chart symbols",
        "warnings":warnings,
    }
