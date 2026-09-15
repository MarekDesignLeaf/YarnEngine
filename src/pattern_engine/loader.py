import json
from pathlib import Path
from .model import Token, PatternRow, PatternDefinition

def load_pattern_dict(data: dict) -> PatternDefinition:
    rows=[]
    for r in data["rows"]:
        rows.append(PatternRow(
            row=int(r["row"]),
            side=r.get("side","NA"),
            sequence=tuple(Token(op=t["op"],n=int(t.get("n",1))) for t in r["sequence"])
        ))
    return PatternDefinition(
        pattern_id=data["pattern_id"],
        version=data["version"],
        name=data["name"],
        repeat_width_stitches=int(data["repeat"]["width_stitches"]),
        repeat_height_rows=int(data["repeat"]["height_rows"]),
        rows=tuple(rows)
    )

def load_pattern_file(path) -> PatternDefinition:
    return load_pattern_dict(json.loads(Path(path).read_text(encoding="utf-8")))
