import sqlite3,json,datetime,uuid
from pathlib import Path
SCHEMA="""
CREATE TABLE IF NOT EXISTS calibration_models(
 model_id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 stage TEXT NOT NULL,
 model_json TEXT NOT NULL,
 validation_json TEXT,
 data_snapshot_json TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 promoted_at TEXT,
 promotion_note TEXT,
 model_schema_version TEXT,
 feature_spec_version TEXT
);
CREATE TABLE IF NOT EXISTS model_stage_history(
 history_id INTEGER PRIMARY KEY AUTOINCREMENT,
 model_id TEXT NOT NULL,
 from_stage TEXT,
 to_stage TEXT NOT NULL,
 changed_at TEXT NOT NULL,
 note TEXT,
 gate_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_models_stage ON calibration_models(stage);
"""
STAGES=("research","candidate","production","retired")
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class ModelRegistry:
 def __init__(self,path):
  Path(path).parent.mkdir(parents=True,exist_ok=True)
  self.conn=sqlite3.connect(str(path),check_same_thread=False);self.conn.row_factory=sqlite3.Row
  self.conn.execute("PRAGMA journal_mode=WAL");self.conn.execute("PRAGMA busy_timeout=5000")
  self.conn.executescript(SCHEMA)
  cols={r[1] for r in self.conn.execute("PRAGMA table_info(calibration_models)")}
  if "model_schema_version" not in cols:self.conn.execute("ALTER TABLE calibration_models ADD COLUMN model_schema_version TEXT")
  if "feature_spec_version" not in cols:self.conn.execute("ALTER TABLE calibration_models ADD COLUMN feature_spec_version TEXT")
  self.conn.commit()
 def close(self):self.conn.close()
 def _row(self,r):
  if not r:return None
  d=dict(r);d["model"]=json.loads(d.pop("model_json"));raw=d.pop("validation_json");d["validation"]=json.loads(raw) if raw else None
  d["data_snapshot"]=json.loads(d.pop("data_snapshot_json"));return d
 def create(self,name,model,validation,data_snapshot,model_schema_version="m8-model-1",feature_spec_version="m8-feature-spec-1"):
  mid="cal_"+uuid.uuid4().hex[:16];ts=now()
  self.conn.execute("""INSERT INTO calibration_models
   (model_id,name,stage,model_json,validation_json,data_snapshot_json,created_at,updated_at,promoted_at,promotion_note,model_schema_version,feature_spec_version)
   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
   (mid,name,"research",json.dumps(model,sort_keys=True),json.dumps(validation,sort_keys=True) if validation else None,
    json.dumps(data_snapshot,sort_keys=True),ts,ts,None,None,model_schema_version,feature_spec_version))
  self.conn.execute("INSERT INTO model_stage_history(model_id,from_stage,to_stage,changed_at,note,gate_json) VALUES(?,?,?,?,?,?)",
                    (mid,None,"research",ts,"model created",None))
  self.conn.commit();return self.get(mid)
 def get(self,mid):return self._row(self.conn.execute("SELECT * FROM calibration_models WHERE model_id=?",(mid,)).fetchone())
 def list(self):return [self._row(r) for r in self.conn.execute("SELECT * FROM calibration_models ORDER BY created_at DESC")]

 def production_gate(self,mid):
  m=self.get(mid)
  if not m:raise KeyError(mid)
  model=m["model"];val=m.get("validation") or {};snap=m.get("data_snapshot") or {}
  reasons=[]
  n=int(model.get("n_samples",0) or 0)
  if n<4:reasons.append("at least 4 calibration samples are required")
  if not model.get("operation_ids"):reasons.append("model has no calibrated operations")
  # Require validation evidence. Accept current LOO/grouped reports if they expose a finite error metric.
  candidates=[]
  def collect(x):
   if isinstance(x,dict):
    for k,v in x.items():
     if k in {"rmse_m","mae_m","mean_absolute_error_m","test_rmse_m","loo_rmse_m"} and isinstance(v,(int,float)):
      candidates.append(float(v))
     collect(v)
   elif isinstance(x,list):
    for v in x:collect(v)
  collect(val)
  if not candidates:reasons.append("independent or cross-validation error evidence is required")
  def find_lists(x,key):
   out=[]
   if isinstance(x,dict):
    if isinstance(x.get(key),list):out.extend(x[key])
    for v in x.values():out.extend(find_lists(v,key))
   return out
  failed=find_lists(val,"failed_folds")
  if failed:reasons.append("validation contains failed folds")
  coverage=snap.get("coverage") if isinstance(snap,dict) else None
  if isinstance(coverage,dict) and coverage.get("undercovered_operations"):
   reasons.append("calibration snapshot reports undercovered operations")
  return {"passed":not reasons,"reasons":reasons,"n_samples":n,"validation_error_metrics":candidates}

 def promote(self,mid,target,note=None):
  if target not in STAGES:raise ValueError("invalid target stage")
  m=self.get(mid)
  if not m:raise KeyError(mid)
  allowed={"research":{"candidate","retired"},"candidate":{"production","research","retired"},"production":{"retired"},"retired":set()}
  if target not in allowed[m["stage"]]:raise ValueError(f"invalid transition {m['stage']} -> {target}")
  gate=None
  if target=="production":
   gate=self.production_gate(mid)
   if not gate["passed"]:raise ValueError("production promotion gate failed: "+"; ".join(gate["reasons"]))
  # Production is exclusive: retire any current production model.
  ts=now()
  if target=="production":
   self.conn.execute("UPDATE calibration_models SET stage='retired',updated_at=? WHERE stage='production' AND model_id<>?",(ts,mid))
  self.conn.execute("UPDATE calibration_models SET stage=?,updated_at=?,promoted_at=?,promotion_note=? WHERE model_id=?",
                    (target,ts,ts,note,mid))
  self.conn.execute("INSERT INTO model_stage_history(model_id,from_stage,to_stage,changed_at,note,gate_json) VALUES(?,?,?,?,?,?)",
                    (mid,m["stage"],target,ts,note,json.dumps(gate,sort_keys=True) if gate else None))
  self.conn.commit();return self.get(mid)

 def history(self,mid):
  return [dict(r) for r in self.conn.execute("SELECT * FROM model_stage_history WHERE model_id=? ORDER BY history_id",(mid,))]

 def production(self):
  r=self.conn.execute("SELECT * FROM calibration_models WHERE stage='production' ORDER BY promoted_at DESC LIMIT 1").fetchone()
  return self._row(r)
