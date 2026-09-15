
import re
from dataclasses import dataclass, asdict
from .abbreviations import ABBREVIATIONS

@dataclass(frozen=True)
class ParseIssue:
    severity: str
    code: str
    message: str
    fragment: str
    row: int | None = None

def _clean_token(s):
    return re.sub(r"\s+"," ",s.strip().upper())

def _parse_atom(atom, registry_ids):
    raw=atom.strip()
    if not raw:
        return None, []
    # Accepted explicit count forms: K, K 4, K4, 4 K, K x4.
    m=re.fullmatch(r"(\d+)\s+(.+)", raw, re.I)
    if m:
        n=int(m.group(1)); name=_clean_token(m.group(2))
    else:
        m=re.fullmatch(r"(.+?)\s*[xX]\s*(\d+)", raw)
        if m:
            name=_clean_token(m.group(1)); n=int(m.group(2))
        else:
            m=re.fullmatch(r"([A-Za-z][A-Za-z0-9_/ -]*?)(\d+)", raw)
            if m and _clean_token(m.group(1)) in ABBREVIATIONS:
                name=_clean_token(m.group(1)); n=int(m.group(2))
            else:
                m=re.fullmatch(r"(.+?)\s+(\d+)", raw)
                if m and _clean_token(m.group(1)) in ABBREVIATIONS:
                    name=_clean_token(m.group(1)); n=int(m.group(2))
                else:
                    name=_clean_token(raw); n=1
    op=ABBREVIATIONS.get(name)
    if not op:
        return None,[ParseIssue("error","UNKNOWN_ABBREVIATION",
            "No conservative canonical mapping exists for this fragment.",raw)]
    if op not in registry_ids:
        return None,[ParseIssue("error","TARGET_OPERATION_UNAVAILABLE",
            f"Mapped operation {op} is not present in the current operation registry.",raw)]
    if n <= 0:
        return None,[ParseIssue("error","INVALID_COUNT","Operation count must be positive.",raw)]
    return {"op":op,"n":n},[]

def parse_row_text(text, registry_ids, row_number=None, side="NA"):
    issues=[]
    if not isinstance(text,str) or not text.strip():
        return {"row":row_number or 1,"side":side,"sequence":[]},[
            asdict(ParseIssue("error","EMPTY_ROW","Row instruction is empty.","",row_number))]
    # Deliberately reject prose constructs requiring semantic interpretation.
    risky=[
        (r"\bREP(?:EAT)?\b|\bTO END\b|\bTO LAST\b","REPEAT_PROSE"),
        (r"[\[\]\(\)\*]","GROUPED_INSTRUCTION"),
        (r"\bUNTIL\b|\bTIMES\b","CONTROL_LANGUAGE"),
        (r"\bRS\b|\bWS\b","SIDE_EMBEDDED"),
    ]
    for pat,code in risky:
        if re.search(pat,text,re.I):
            issues.append(ParseIssue("error",code,
                "Instruction contains control/grouping prose that requires reviewed interpretation.",text,row_number))
    if issues:
        return {"row":row_number or 1,"side":side,"sequence":[]},[asdict(x) for x in issues]

    atoms=[x.strip() for x in re.split(r"[,;]",text) if x.strip()]
    sequence=[]
    for atom in atoms:
        tok,errs=_parse_atom(atom,registry_ids)
        if tok: sequence.append(tok)
        issues.extend(ParseIssue(e.severity,e.code,e.message,e.fragment,row_number) for e in errs)
    return {"row":row_number or 1,"side":side,"sequence":sequence},[asdict(x) for x in issues]

def parse_rows(rows, registry_ids):
    out=[];issues=[]
    for i,r in enumerate(rows,1):
        if isinstance(r,str):
            text=r; row=i; side="NA"
        else:
            text=r.get("instruction","");row=int(r.get("row",i));side=str(r.get("side","NA")).upper()
        parsed,errs=parse_row_text(text,registry_ids,row,side)
        out.append(parsed);issues.extend(errs)
    return {"rows":out,"issues":issues,"valid":not any(x["severity"]=="error" for x in issues)}
