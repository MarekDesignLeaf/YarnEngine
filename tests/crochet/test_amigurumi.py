from pathlib import Path
from src.pattern_engine.registry import load_operation_registry
from src.crochet.amigurumi import analyse_rounds
OPS=load_operation_registry(Path(__file__).resolve().parents[2]/"data/stitches/operations.seed.json")
def test_sc_round():
 r=analyse_rounds({"initial_stitches":6,"rounds":[{"operations":{"SC":6}}]},OPS)
 assert r["valid"] and r["final_stitches"]==6
def test_increase_round():
 r=analyse_rounds({"initial_stitches":6,"rounds":[{"operations":{"SC_INC":6}}]},OPS)
 assert r["valid"] and r["final_stitches"]==12
def test_decrease_round():
 r=analyse_rounds({"initial_stitches":12,"rounds":[{"operations":{"SC2TOG":6}}]},OPS)
 assert r["valid"] and r["final_stitches"]==6
def test_mixed_shaping_round():
 r=analyse_rounds({"initial_stitches":12,"rounds":[{"operations":{"SC":6,"SC2TOG":3}}]},OPS)
 assert r["valid"] and r["final_stitches"]==9
def test_input_mismatch():
 r=analyse_rounds({"initial_stitches":10,"rounds":[{"operations":{"SC":9}}]},OPS)
 assert not r["valid"]
