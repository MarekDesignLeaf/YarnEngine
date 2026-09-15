from src.toy_assembly.bom import aggregate_toy_bom
def test_toy_parts_and_assembly():
 r=aggregate_toy_bom([{"part_id":"body","yarn_consumption_m":{"A":20}},{"part_id":"head","yarn_consumption_m":{"A":10,"B":2}}],
 [{"kind":"sewing","yarn_id":"A","length_m":1.5}])
 assert r["total_yarn_m"]=={"A":31.5,"B":2.0}
