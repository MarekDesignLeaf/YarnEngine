"""Minimal human-readable Pattern DSL.

Syntax:
PATTERN <ID>
NAME <free text>
VERSION <semver>
REPEAT <width>x<height>
ROW <number> <side>: K4 P2 C2_2R1 P2 K4

Token form is OP followed by positive integer count.
Operation ids may contain letters, digits and underscores.
"""
import re
from src.pattern_engine.model import Token,PatternRow,PatternDefinition

TOKEN_RE=re.compile(r"^([A-Z][A-Z0-9_]*?)(\d+)$")

def parse_pattern_text(text: str) -> PatternDefinition:
    pattern_id=name=version=None
    rw=rh=None
    rows=[]
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("PATTERN "):
            pattern_id=line.split(None,1)[1].strip()
        elif line.startswith("NAME "):
            name=line.split(None,1)[1].strip()
        elif line.startswith("VERSION "):
            version=line.split(None,1)[1].strip()
        elif line.startswith("REPEAT "):
            val=line.split(None,1)[1].lower().replace(" ","")
            a,b=val.split("x",1); rw=int(a); rh=int(b)
        elif line.startswith("ROW "):
            head,body=line.split(":",1)
            parts=head.split()
            row_no=int(parts[1]); side=parts[2]
            seq=[]
            for rawtok in body.split():
                m=TOKEN_RE.match(rawtok)
                if not m:
                    raise ValueError(f"invalid token {rawtok}")
                seq.append(Token(m.group(1),int(m.group(2))))
            rows.append(PatternRow(row_no,side,tuple(seq)))
        else:
            raise ValueError(f"unknown DSL line: {line}")
    if not all([pattern_id,name,version]) or rw is None or rh is None:
        raise ValueError("PATTERN, NAME, VERSION and REPEAT are required")
    return PatternDefinition(pattern_id,version,name,rw,rh,tuple(rows))
