from src.pattern_acquisition.parser import parse_row_text,parse_rows
OPS={"K","P","YO","K2TOG","C2_2R"}
def test_exact_abbreviations():
 row,issues=parse_row_text("K 4, P2, YO",OPS,1,"RS")
 assert not issues and row["sequence"]==[{"op":"K","n":4},{"op":"P","n":2},{"op":"YO","n":1}]
def test_cable_mapping():
 row,issues=parse_row_text("C2/2R",OPS)
 assert not issues and row["sequence"][0]["op"]=="C2_2R"
def test_unknown_requires_review():
 row,issues=parse_row_text("MAGICSTITCH 3",OPS)
 assert issues[0]["code"]=="UNKNOWN_ABBREVIATION"
def test_repeat_prose_rejected():
 row,issues=parse_row_text("K2, P2, repeat to end",OPS)
 assert any(x["code"]=="REPEAT_PROSE" for x in issues)
def test_grouping_rejected():
 row,issues=parse_row_text("[K2, P2] x4",OPS)
 assert any(x["code"]=="GROUPED_INSTRUCTION" for x in issues)
