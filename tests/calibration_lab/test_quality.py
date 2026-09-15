from src.calibration_lab.quality import replicate_quality
def test_replicate_flags():
 rows=[{"replicate_group_id":"G","yarn_length_m":10},{"replicate_group_id":"G","yarn_length_m":10.1}]
 d=replicate_quality(rows);assert d["groups"][0]["n"]==2
 assert d["flags"][0]["code"]=="insufficient_replicates"
