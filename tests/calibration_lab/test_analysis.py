from types import SimpleNamespace
from src.calibration_lab.analysis import derive_operation_counts,readiness
def test_operation_counts_whole_repeats():
 p=SimpleNamespace(repeat_width_stitches=2,repeat_height_rows=2,
 rows=(SimpleNamespace(sequence=(SimpleNamespace(op="K",n=2),)),SimpleNamespace(sequence=(SimpleNamespace(op="P",n=2),))))
 assert derive_operation_counts(p,20,20)=={"K":200,"P":200}
def test_readiness_gate():
 assert readiness([])["ready"] is False
