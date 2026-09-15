import pytest
from src.model_registry.store import ModelRegistry

GOOD_MODEL={"n_samples":10,"operation_ids":["K"],"rmse_m":0.1}
GOOD_VALIDATION={"grouped_holdout":{"rmse_m":0.2}}
GOOD_SNAPSHOT={"swatch_ids":list(range(10))}

def test_lifecycle(tmp_path):
 s=ModelRegistry(tmp_path/"m.sqlite")
 m=s.create("M",GOOD_MODEL,GOOD_VALIDATION,GOOD_SNAPSHOT)
 assert m["stage"]=="research"
 m=s.promote(m["model_id"],"candidate","review");assert m["stage"]=="candidate"
 m=s.promote(m["model_id"],"production","approved");assert m["stage"]=="production"
 assert s.history(m["model_id"])[-1]["to_stage"]=="production"
 m=s.promote(m["model_id"],"retired","old");assert m["stage"]=="retired"
 with pytest.raises(ValueError):s.promote(m["model_id"],"production")
 s.close()

def test_production_gate_blocks_weak_model(tmp_path):
 s=ModelRegistry(tmp_path/"m.sqlite")
 m=s.create("weak",{"n_samples":1,"operation_ids":[]},None,{})
 s.promote(m["model_id"],"candidate")
 with pytest.raises(ValueError,match="production promotion gate failed"):
  s.promote(m["model_id"],"production")

def test_exclusive_production(tmp_path):
 s=ModelRegistry(tmp_path/"m.sqlite")
 a=s.create("A",GOOD_MODEL,GOOD_VALIDATION,GOOD_SNAPSHOT)
 b=s.create("B",GOOD_MODEL,GOOD_VALIDATION,GOOD_SNAPSHOT)
 for x in (a,b):s.promote(x["model_id"],"candidate")
 s.promote(a["model_id"],"production");s.promote(b["model_id"],"production")
 assert s.get(a["model_id"])["stage"]=="retired";assert s.get(b["model_id"])["stage"]=="production"
