import sqlite3, json, datetime, hashlib
from pathlib import Path

SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS projects(
  project_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  description TEXT,
  pattern_id TEXT NOT NULL,
  pattern_version TEXT NOT NULL,
  yarn_id TEXT,
  request_json TEXT NOT NULL,
  result_json TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  request_hash TEXT,
  result_request_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_projects_pattern ON projects(pattern_id,pattern_version);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
"""


def request_fingerprint(request):
    raw=json.dumps(request,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

class ProjectStore:
    def __init__(self,path):
        self.path=str(path)
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory=sqlite3.Row
        self.conn.executescript(SCHEMA)
        cols={r["name"] for r in self.conn.execute("PRAGMA table_info(projects)")}
        if "request_hash" not in cols:self.conn.execute("ALTER TABLE projects ADD COLUMN request_hash TEXT")
        if "result_request_hash" not in cols:self.conn.execute("ALTER TABLE projects ADD COLUMN result_request_hash TEXT")
        self.conn.commit()

    def close(self): self.conn.close()

    def create(self,name,description,pattern_id,pattern_version,yarn_id,request,result=None,status="draft"):
        now=utc_now()
        cur=self.conn.execute(
            """INSERT INTO projects(name,description,pattern_id,pattern_version,yarn_id,request_json,result_json,status,created_at,updated_at,request_hash,result_request_hash)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (name,description,pattern_id,pattern_version,yarn_id,json.dumps(request,sort_keys=True),
             json.dumps(result,sort_keys=True) if result is not None else None,status,now,now,
             request_fingerprint(request),request_fingerprint(request) if result is not None else None))
        self.conn.commit()
        return self.get(cur.lastrowid)

    def get(self,project_id):
        row=self.conn.execute("SELECT * FROM projects WHERE project_id=?",(project_id,)).fetchone()
        if not row: return None
        d=dict(row)
        d["request"]=json.loads(d.pop("request_json"))
        raw=d.pop("result_json")
        d["result"]=json.loads(raw) if raw else None
        if not d.get("request_hash"): d["request_hash"]=request_fingerprint(d["request"])
        d["result_stale"]=bool(d["result"] is not None and d.get("result_request_hash") != d.get("request_hash"))
        return d

    def list(self,limit=100):
        rows=self.conn.execute(
          "SELECT * FROM projects ORDER BY updated_at DESC, project_id DESC LIMIT ?",(limit,)).fetchall()
        out=[]
        for row in rows:
            d=dict(row)
            d["request"]=json.loads(d.pop("request_json"))
            raw=d.pop("result_json")
            d["result"]=json.loads(raw) if raw else None
            if not d.get("request_hash"): d["request_hash"]=request_fingerprint(d["request"])
            d["result_stale"]=bool(d["result"] is not None and d.get("result_request_hash") != d.get("request_hash"))
            out.append(d)
        return out

    def update(self,project_id,**changes):
        current=self.get(project_id)
        if current is None: return None
        allowed={"name","description","pattern_id","pattern_version","yarn_id","status"}
        data={k:v for k,v in changes.items() if k in allowed}
        if "request" in changes:
            data["request_json"]=json.dumps(changes["request"],sort_keys=True)
            data["request_hash"]=request_fingerprint(changes["request"])
            # Any input change invalidates a previously stored result.
            if "result" not in changes:
                data["result_json"]=None
                data["result_request_hash"]=None
        if "result" in changes:
            data["result_json"]=json.dumps(changes["result"],sort_keys=True) if changes["result"] is not None else None
            effective_request=changes.get("request",current["request"])
            data["result_request_hash"]=request_fingerprint(effective_request) if changes["result"] is not None else None
        data["updated_at"]=utc_now()
        sets=",".join(f"{k}=?" for k in data)
        vals=list(data.values())+[project_id]
        self.conn.execute(f"UPDATE projects SET {sets} WHERE project_id=?",vals)
        self.conn.commit()
        return self.get(project_id)

    def delete(self,project_id):
        cur=self.conn.execute("DELETE FROM projects WHERE project_id=?",(project_id,))
        self.conn.commit()
        return cur.rowcount>0
