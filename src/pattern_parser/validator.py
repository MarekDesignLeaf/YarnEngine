def validate_pattern_structure(pattern, operations):
    errors=[]
    if len(pattern["rows"]) != pattern["repeat"]["height_rows"]:
        errors.append("row count mismatch")
    width=pattern["repeat"]["width_stitches"]
    for row in pattern["rows"]:
        consumed=produced=0
        for token in row["sequence"]:
            op=operations.get(token["op"])
            if not op:
                errors.append(f"row {row['row']}: unknown operation {token['op']}")
                continue
            consumed += op["consumes_stitches"]*token["n"]
            produced += op["produces_stitches"]*token["n"]
        if consumed != width or produced != width:
            errors.append(f"row {row['row']}: width={width}, consumed={consumed}, produced={produced}")
    return errors
