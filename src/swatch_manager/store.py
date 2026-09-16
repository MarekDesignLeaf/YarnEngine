import sqlite3,json,datetime
from pathlib import Path
SCHEMA="""
CREATE TABLE IF NOT EXISTS swatches(
 swatch_id INTEGER PRIMARY KEY AUTOINCREMENT,
 name TEXT NOT NULL,
 pattern_id TEXT NOT NULL,
 pattern_version TEXT NOT NULL,
 yarn_id TEXT NOT NULL,
 needle_mm REAL,
 stitches INTEGER NOT NULL,
 rows INTEGER NOT NULL,
 width_cm REAL NOT NULL,
 height_cm REAL NOT NULL,
 yarn_length_m REAL,
 yarn_mass_g REAL,
 notes TEXT,
 evidence_method TEXT NOT NULL DEFAULT 'measured',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_swatches_pattern ON swatches(pattern_id,pattern_version);
CREATE INDEX IF NOT EXISTS idx_swatches_yarn ON swatches(yarn_id);
"""
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
class SwatchStore:
 def __init__(self,path):
  Path(path).parent.mkdir(parents=True,exist_ok=True)
  self.conn=sqlite3.connect(str(path),check_same_thread=False);self.conn.row_factory=sqlite3.Row
  self.conn.execute("PRAGMA journal_mode=WAL");self.conn.execute("PRAGMA busy_timeout=5000")
  self.conn.executescript(SCHEMA)
  cols={r[1] for r in self.conn.execute("PRAGMA table_info(swatches)")}
  for name,sql in [
    ("replicate_group_id","ALTER TABLE swatches ADD COLUMN replicate_group_id TEXT"),
    ("operator_id","ALTER TABLE swatches ADD COLUMN operator_id TEXT"),
    ("condition","ALTER TABLE swatches ADD COLUMN condition TEXT DEFAULT 'unknown"),
    ("instrument_id","ALTER TABLE swatches ADD COLUMN instrument_id TEXT"),
    ("photo_reference","ALTER TABLE swatches ADD COLUMN photo_reference TEXT")]:
   if name not in cols:
    # condition statement is handled separately below to keep SQLite default syntax simple
    if name=="condition": self.conn.execute("ALTER TABLE swatches ADD COLUMN condition TEXT DEFAULT 'unknown'")
    else: self.conn.execute(sql)
  self.conn.commit()
 def close(self):self.conn.close()
 def create(self,d):
  ts=now()
  cur=self.conn.execute("""INSERT INTO swatches(name,pattern_id,pattern_version,yarn_id,needle_mm,stitches,rows,width_cm,height_cm,yarn_length_m,yarn_mass_g,notes,evidence_method,created_at,updated_at)
 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(d["name"],d["pattern_id"],d["pattern_version"],d["yarn_id"],d.get("needle_mm"),d["stitches"],d["rows"],d["width_cm"],d["height_cm"],d.get("yarn_length_m"),d.get("yarn_mass_g"),d.get("notes"),d.get("evidence_method","measured"),ts,ts))
  self.conn.commit();return self.get(cur.lastrowid)
 def get(self,i):
  r=self.conn.execute("SELECT * FROM swatches WHERE swatch_id=?",(i,)).fetchone();return dict(r) if r else None
 def list(self):
  return [dict(r) for r in self.conn.execute("SELECT * FROM swatches ORDER BY updated_at DESC,swatch_id DESC")]
 def delete(self,i):
  c=self.conn.execute("DELETE FROM swatches WHERE swatch_id=?",(i,));self.conn.commit();return c.rowcount>0

 def set_calibration_metadata(self,i,replicate_group_id=None,operator_id=None,condition="unknown",instrument_id=None,photo_reference=None):
  if condition not in {"unblocked","blocked","washed","relaxed","unknown"}: raise ValueError("invalid condition")
  self.conn.execute("""UPDATE swatches SET replicate_group_id=?,operator_id=?,condition=?,instrument_id=?,photo_reference=?,updated_at=?
   WHERE swatch_id=?""",(replicate_group_id,operator_id,condition,instrument_id,photo_reference,now(),i))
  self.conn.commit();return self.get(i)
