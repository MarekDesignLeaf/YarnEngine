import sqlite3,json,datetime
from pathlib import Path
from .record import CrochetCalibrationRecord

SCHEMA="""CREATE TABLE IF NOT EXISTS crochet_calibration(
 record_id TEXT PRIMARY KEY, replicate_group_id TEXT NOT NULL, crocheter_id TEXT NOT NULL, yarn_id TEXT NOT NULL,
 hook_mm REAL NOT NULL, gauge_stitches INTEGER NOT NULL, gauge_rows INTEGER NOT NULL,
 gauge_width_mm REAL NOT NULL, gauge_height_mm REAL NOT NULL, operation_counts_json TEXT NOT NULL,
 yarn_length_m REAL NOT NULL, yarn_mass_g REAL, tex REAL, yarn_diameter_mm REAL,
 construction TEXT NOT NULL, tension_condition TEXT NOT NULL, evidence_reference TEXT,
 created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_crochet_cal_group ON crochet_calibration(replicate_group_id);
CREATE INDEX IF NOT EXISTS idx_crochet_cal_yarn ON crochet_calibration(yarn_id);"""

class CrochetCalibrationStore:
 def __init__(self,path):
  Path(path).parent.mkdir(parents=True,exist_ok=True);self.conn=sqlite3.connect(str(path),check_same_thread=False)
  self.conn.row_factory=sqlite3.Row;self.conn.executescript(SCHEMA);self.conn.commit()
 def close(self):self.conn.close()
 def add(self,r):
  if not isinstance(r,CrochetCalibrationRecord):raise TypeError("CrochetCalibrationRecord required")
  self.conn.execute("""INSERT INTO crochet_calibration VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
   (r.record_id,r.replicate_group_id,r.crocheter_id,r.yarn_id,r.hook_mm,r.gauge_stitches,r.gauge_rows,
    r.gauge_width_mm,r.gauge_height_mm,json.dumps(dict(r.operation_counts),sort_keys=True),r.yarn_length_m,
    r.yarn_mass_g,r.tex,r.yarn_diameter_mm,r.construction,r.tension_condition,r.evidence_reference,
    datetime.datetime.now(datetime.timezone.utc).isoformat()))
  self.conn.commit();return self.get(r.record_id)
 def get(self,rid):
  x=self.conn.execute("SELECT * FROM crochet_calibration WHERE record_id=?",(rid,)).fetchone()
  return self._dict(x) if x else None
 def list(self):
  return [self._dict(x) for x in self.conn.execute("SELECT * FROM crochet_calibration ORDER BY created_at")]
 def delete(self,rid):
  c=self.conn.execute("DELETE FROM crochet_calibration WHERE record_id=?",(rid,));self.conn.commit();return c.rowcount>0
 def records(self):
  out=[]
  for x in self.list():
   y={k:v for k,v in x.items() if k!="created_at"};out.append(CrochetCalibrationRecord(**y))
  return out
 def _dict(self,x):
  d=dict(x);d["operation_counts"]=json.loads(d.pop("operation_counts_json"));return d
