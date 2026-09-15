
import re
from dataclasses import dataclass, asdict
from src.pattern_acquisition.abbreviations import ABBREVIATIONS

@dataclass(frozen=True)
class GrammarIssue:
    severity: str
    code: str
    message: str
    fragment: str
    row: int | None = None

def _canon_name(s):
    return re.sub(r"\s+"," ",s.strip().upper())

def _parse_atom(raw, operations, row=None):
    raw=raw.strip()
    if not raw:
        return [],[]
    n=1
    m=re.fullmatch(r"(\d+)\s+(.+)",raw,re.I)
    if m:
        n=int(m.group(1));name=_canon_name(m.group(2))
    else:
        m=re.fullmatch(r"(.+?)\s*[xX]\s*(\d+)",raw)
        if m and not raw.lstrip().startswith(("(", "[")):
            name=_canon_name(m.group(1));n=int(m.group(2))
        else:
            m=re.fullmatch(r"([A-Za-z][A-Za-z0-9_/ -]*?)(\d+)",raw)
            if m and _canon_name(m.group(1)) in ABBREVIATIONS:
                name=_canon_name(m.group(1));n=int(m.group(2))
            else:
                m=re.fullmatch(r"(.+?)\s+(\d+)",raw)
                if m and _canon_name(m.group(1)) in ABBREVIATIONS:
                    name=_canon_name(m.group(1));n=int(m.group(2))
                else:
                    name=_canon_name(raw)
    op=ABBREVIATIONS.get(name)
    if not op:
        return [],[GrammarIssue("error","UNKNOWN_ABBREVIATION","No canonical operation mapping exists.",raw,row)]
    if op not in operations:
        return [],[GrammarIssue("error","TARGET_OPERATION_UNAVAILABLE",f"{op} is not in the operation registry.",raw,row)]
    if n<=0:
        return [],[GrammarIssue("error","INVALID_COUNT","Operation count must be positive.",raw,row)]
    return [{"op":op,"n":n}],[]

def _split_top_level(text):
    parts=[];buf=[];depth=0;open_char=None
    pairs={"(":")","[":"]"}
    for ch in text:
        if ch in pairs:
            if depth!=0:
                raise ValueError("nested groups are not supported")
            depth=1;open_char=ch;buf.append(ch)
        elif ch in ")]":
            if depth!=1 or pairs.get(open_char)!=ch:
                raise ValueError("unbalanced group delimiters")
            depth=0;buf.append(ch)
        elif ch in ",;" and depth==0:
            s="".join(buf).strip()
            if s:parts.append(s)
            buf=[]
        else:
            buf.append(ch)
    if depth:raise ValueError("unbalanced group delimiters")
    s="".join(buf).strip()
    if s:parts.append(s)
    return parts

def _consumed(sequence, operations):
    return sum(int(operations[t["op"]]["consumes_stitches"])*int(t["n"]) for t in sequence)

def _merge_adjacent(seq):
    out=[]
    for t in seq:
        if out and out[-1]["op"]==t["op"]:
            out[-1]={"op":t["op"],"n":out[-1]["n"]+t["n"]}
        else:
            out.append(dict(t))
    return out

def _parse_unit(part, operations, row=None):
    part=part.strip()
    gm=re.fullmatch(r"[\(\[](.+)[\)\]]\s*(?:[xX]\s*(\d+)|(\d+)\s*times?)",part,re.I)
    if gm:
        inner=gm.group(1);mult=int(gm.group(2) or gm.group(3))
        if mult<=0:
            return [],[GrammarIssue("error","INVALID_REPEAT_COUNT","Group repeat count must be positive.",part,row)]
        seq=[];issues=[]
        try:parts=_split_top_level(inner)
        except ValueError as e:
            return [],[GrammarIssue("error","GROUP_SYNTAX",str(e),part,row)]
        for atom in parts:
            toks,errs=_parse_atom(atom,operations,row);seq.extend(toks);issues.extend(errs)
        return _merge_adjacent(seq*mult),issues
    if part.startswith(("(", "[")) or ")" in part or "]" in part:
        return [],[GrammarIssue("error","GROUP_REPEAT_REQUIRED","A group must have an explicit repeat count such as (K2, P2) x4.",part,row)]
    return _parse_atom(part,operations,row)

def parse_advanced_row(text, operations, repeat_width_stitches, row_number=None, side="NA"):
    if not isinstance(text,str) or not text.strip():
        return {"row":row_number or 1,"side":side,"sequence":[]},[
            asdict(GrammarIssue("error","EMPTY_ROW","Row instruction is empty.","",row_number))]
    if re.search(r"\bUNTIL\b|\bTO LAST\b",text,re.I):
        return {"row":row_number or 1,"side":side,"sequence":[]},[
            asdict(GrammarIssue("error","UNSUPPORTED_CONTROL_LANGUAGE","This control phrase still requires manual review.",text,row_number))]
    if re.search(r"\bRS\b|\bWS\b",text,re.I):
        return {"row":row_number or 1,"side":side,"sequence":[]},[
            asdict(GrammarIssue("error","SIDE_EMBEDDED","RS/WS must be supplied as row metadata, not parsed from prose.",text,row_number))]

    repeat_to_end=bool(re.search(r"(?:,\s*)?\brep(?:eat)?\s+to\s+end\s*$",text,re.I))
    body=re.sub(r"(?:,\s*)?\brep(?:eat)?\s+to\s+end\s*$","",text,flags=re.I).strip()
    try:
        parts=_split_top_level(body)
    except ValueError as e:
        return {"row":row_number or 1,"side":side,"sequence":[]},[
            asdict(GrammarIssue("error","GROUP_SYNTAX",str(e),text,row_number))]

    seq=[];issues=[]
    for part in parts:
        toks,errs=_parse_unit(part,operations,row_number)
        seq.extend(toks);issues.extend(errs)
    if issues:
        return {"row":row_number or 1,"side":side,"sequence":seq},[asdict(x) for x in issues]

    if repeat_to_end:
        unit_width=_consumed(seq,operations)
        if unit_width<=0:
            issues.append(GrammarIssue("error","ZERO_WIDTH_REPEAT","Repeat unit consumes zero stitches and cannot fill a row.",body,row_number))
        elif not repeat_width_stitches or repeat_width_stitches<=0:
            issues.append(GrammarIssue("error","REPEAT_WIDTH_REQUIRED","repeat to end requires declared repeat width.",body,row_number))
        elif repeat_width_stitches % unit_width != 0:
            issues.append(GrammarIssue("error","REPEAT_DOES_NOT_TILE_WIDTH",
                f"Repeat unit consumes {unit_width} stitches and cannot exactly tile declared width {repeat_width_stitches}.",body,row_number))
        else:
            seq=_merge_adjacent(seq*(repeat_width_stitches//unit_width))

    return {"row":row_number or 1,"side":side,"sequence":_merge_adjacent(seq)},[asdict(x) for x in issues]

def parse_advanced_rows(rows, operations, repeat_width_stitches):
    out=[];issues=[]
    for i,r in enumerate(rows,1):
        if isinstance(r,str):
            text=r;row=i;side="NA"
        else:
            text=r.get("instruction","");row=int(r.get("row",i));side=str(r.get("side","NA")).upper()
        parsed,errs=parse_advanced_row(text,operations,repeat_width_stitches,row,side)
        out.append(parsed);issues.extend(errs)
    return {"rows":out,"issues":issues,"valid":not any(x["severity"]=="error" for x in issues)}
