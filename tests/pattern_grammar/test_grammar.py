from src.pattern_grammar.grammar import parse_advanced_row,parse_advanced_rows

OPS={
"K":{"consumes_stitches":1,"produces_stitches":1},
"P":{"consumes_stitches":1,"produces_stitches":1},
"YO":{"consumes_stitches":0,"produces_stitches":1},
"K2TOG":{"consumes_stitches":2,"produces_stitches":1},
"C2_2R":{"consumes_stitches":4,"produces_stitches":4},
}

def test_parenthesized_group_repeat():
 row,issues=parse_advanced_row("(K2, P2) x4",OPS,16,1,"RS")
 assert not issues
 assert row["sequence"]==[{"op":"K","n":2},{"op":"P","n":2},{"op":"K","n":2},{"op":"P","n":2},{"op":"K","n":2},{"op":"P","n":2},{"op":"K","n":2},{"op":"P","n":2}]

def test_bracket_group_repeat():
 row,issues=parse_advanced_row("[K2, P2] 2 times",OPS,8)
 assert not issues and sum(x["n"] for x in row["sequence"])==8

def test_repeat_to_end_exact_tiles():
 row,issues=parse_advanced_row("K2, P2, repeat to end",OPS,12)
 assert not issues
 assert sum(OPS[x["op"]]["consumes_stitches"]*x["n"] for x in row["sequence"])==12

def test_repeat_to_end_non_tiling_rejected():
 row,issues=parse_advanced_row("K2, P2, repeat to end",OPS,10)
 assert any(x["code"]=="REPEAT_DOES_NOT_TILE_WIDTH" for x in issues)

def test_zero_width_repeat_rejected():
 row,issues=parse_advanced_row("YO, repeat to end",OPS,10)
 assert any(x["code"]=="ZERO_WIDTH_REPEAT" for x in issues)

def test_group_without_multiplier_rejected():
 row,issues=parse_advanced_row("(K2, P2)",OPS,4)
 assert any(x["code"]=="GROUP_REPEAT_REQUIRED" for x in issues)

def test_nested_groups_rejected():
 row,issues=parse_advanced_row("((K2,P2) x2) x2",OPS,16)
 assert any(x["code"]=="GROUP_SYNTAX" for x in issues)

def test_unsupported_until_review():
 row,issues=parse_advanced_row("K2 until last 2",OPS,10)
 assert any(x["code"]=="UNSUPPORTED_CONTROL_LANGUAGE" for x in issues)

def test_cable_atom():
 row,issues=parse_advanced_row("C2/2R",OPS,4)
 assert not issues and row["sequence"]==[{"op":"C2_2R","n":1}]
