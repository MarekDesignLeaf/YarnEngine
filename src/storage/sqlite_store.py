import sqlite3, json, math
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS yarns(
  yarn_id TEXT PRIMARY KEY,
  brand TEXT NOT NULL,
  product TEXT NOT NULL,
  variant TEXT,
  cyc_weight INTEGER,
  package_mass_g REAL NOT NULL,
  package_length_m REAL NOT NULL,
  tex REAL,
  nominal_diameter_mm REAL,
  wpi REAL,
  recommended_needle_min_mm REAL,
  recommended_needle_max_mm REAL,
  fibre_json TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_reference TEXT,
  evidence_level TEXT NOT NULL,
  checksum TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patterns(
  pattern_id TEXT NOT NULL,
  version TEXT NOT NULL,
  name TEXT NOT NULL,
  family_id TEXT NOT NULL,
  difficulty TEXT NOT NULL,
  tags_json TEXT NOT NULL,
  techniques_json TEXT NOT NULL,
  pattern_json TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_reference TEXT,
  license_id TEXT,
  checksum TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(pattern_id,version)
);

CREATE TABLE IF NOT EXISTS provenance_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  version TEXT,
  source_type TEXT,
  source_reference TEXT,
  license_id TEXT,
  evidence_level TEXT,
  checksum TEXT NOT NULL,
  imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_type TEXT,
  source_file TEXT,
  raw_json TEXT,
  error_code TEXT NOT NULL,
  error_message TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS yarn_suppliers(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  yarn_id TEXT NOT NULL,
  name TEXT NOT NULL,
  price_amount REAL,
  price_currency TEXT,
  product_url TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings(
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE TABLE IF NOT EXISTS stash(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  yarn_id TEXT NOT NULL,
  quantity_g REAL,
  quantity_skeins REAL,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(user_id,yarn_id)
);

CREATE TABLE IF NOT EXISTS product_lines(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  photo_url TEXT,
  product_url TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS product_line_materials(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_line_id INTEGER NOT NULL,
  yarn_id TEXT NOT NULL,
  length_m REAL,
  quantity_g REAL,
  notes TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_yarns_brand_product ON yarns(brand,product);
CREATE INDEX IF NOT EXISTS idx_yarns_weight ON yarns(cyc_weight);
CREATE INDEX IF NOT EXISTS idx_yarn_suppliers_yarn ON yarn_suppliers(yarn_id);
CREATE INDEX IF NOT EXISTS idx_product_lines_name ON product_lines(name);
CREATE INDEX IF NOT EXISTS idx_product_line_materials_line ON product_line_materials(product_line_id);
CREATE INDEX IF NOT EXISTS idx_patterns_family ON patterns(family_id);
CREATE INDEX IF NOT EXISTS idx_patterns_active ON patterns(active);

CREATE VIRTUAL TABLE IF NOT EXISTS pattern_fts USING fts5(
  pattern_id UNINDEXED,
  version UNINDEXED,
  name,
  family_id,
  tags,
  techniques
);

CREATE VIRTUAL TABLE IF NOT EXISTS yarn_fts USING fts5(
  yarn_id UNINDEXED,
  brand,
  product,
  variant
);
"""

YARN_EXTRA_COLUMNS = {
    "description": "TEXT",
    "photo_url": "TEXT",
    "product_line": "TEXT",
    "price_amount": "REAL",
    "price_currency": "TEXT",
}


class SQLiteStore:
    def __init__(self,path):
        self.path=str(path)
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        self.conn=sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.row_factory=sqlite3.Row
        self.conn.executescript(SCHEMA)
        cols={r["name"] for r in self.conn.execute("PRAGMA table_info(yarns)")}
        for name,coltype in YARN_EXTRA_COLUMNS.items():
            if name not in cols:
                self.conn.execute(f"ALTER TABLE yarns ADD COLUMN {name} {coltype}")
        self.conn.commit()

    def close(self): self.conn.close()

    def upsert_yarn(self,yarn_dict,checksum,now):
        c=self.conn.cursor()
        c.execute("""
        INSERT INTO yarns(yarn_id,brand,product,variant,cyc_weight,package_mass_g,package_length_m,tex,
        nominal_diameter_mm,wpi,recommended_needle_min_mm,recommended_needle_max_mm,fibre_json,
        source_type,source_reference,evidence_level,checksum,created_at,updated_at,
        description,photo_url,product_line,price_amount,price_currency)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(yarn_id) DO UPDATE SET
          brand=excluded.brand,product=excluded.product,variant=excluded.variant,cyc_weight=excluded.cyc_weight,
          package_mass_g=excluded.package_mass_g,package_length_m=excluded.package_length_m,tex=excluded.tex,
          nominal_diameter_mm=excluded.nominal_diameter_mm,wpi=excluded.wpi,
          recommended_needle_min_mm=excluded.recommended_needle_min_mm,
          recommended_needle_max_mm=excluded.recommended_needle_max_mm,
          fibre_json=excluded.fibre_json,source_type=excluded.source_type,source_reference=excluded.source_reference,
          evidence_level=excluded.evidence_level,checksum=excluded.checksum,updated_at=excluded.updated_at,
          description=COALESCE(description,excluded.description),
          photo_url=COALESCE(photo_url,excluded.photo_url),
          product_line=COALESCE(product_line,excluded.product_line),
          price_amount=COALESCE(price_amount,excluded.price_amount),
          price_currency=COALESCE(price_currency,excluded.price_currency)
        """,(
          yarn_dict["yarn_id"],yarn_dict["brand"],yarn_dict["product"],yarn_dict.get("variant"),
          yarn_dict.get("cyc_weight"),yarn_dict["package_mass_g"],yarn_dict["package_length_m"],
          yarn_dict.get("tex"),yarn_dict.get("nominal_diameter_mm"),yarn_dict.get("wpi"),
          yarn_dict.get("recommended_needle_min_mm"),yarn_dict.get("recommended_needle_max_mm"),
          json.dumps(yarn_dict["fibre_composition"],sort_keys=True),
          yarn_dict.get("source_type","user"),yarn_dict.get("source_reference"),
          yarn_dict.get("evidence_level","declared"),checksum,now,now,
          yarn_dict.get("description"),yarn_dict.get("photo_url"),yarn_dict.get("product_line"),
          yarn_dict.get("price_amount"),yarn_dict.get("price_currency"),
        ))
        c.execute("DELETE FROM yarn_fts WHERE yarn_id=?",(yarn_dict["yarn_id"],))
        c.execute("INSERT INTO yarn_fts(yarn_id,brand,product,variant) VALUES(?,?,?,?)",
                  (yarn_dict["yarn_id"],yarn_dict["brand"],yarn_dict["product"],yarn_dict.get("variant") or ""))
        self.conn.commit()

    def update_yarn_extra(self,yarn_id,**fields):
        """Update only the collaborative/editorial yarn fields (description, photo, product
        line, indicative price) without touching the structural/technical fields that came
        from a sourced import."""
        allowed={k:v for k,v in fields.items() if k in YARN_EXTRA_COLUMNS}
        if not allowed:
            return self.get_yarn(yarn_id)
        sets=",".join(f"{k}=?" for k in allowed)
        vals=list(allowed.values())+[yarn_id]
        c=self.conn.cursor()
        c.execute(f"UPDATE yarns SET {sets} WHERE yarn_id=?",vals)
        self.conn.commit()
        return self.get_yarn(yarn_id) if c.rowcount>0 else None

    def get_yarn(self,yarn_id):
        r=self.conn.execute("SELECT * FROM yarns WHERE yarn_id=?",(yarn_id,)).fetchone()
        return dict(r) if r is not None else None

    def delete_yarn(self,yarn_id):
        c=self.conn.cursor()
        c.execute("DELETE FROM yarn_fts WHERE yarn_id=?",(yarn_id,))
        c.execute("DELETE FROM yarns WHERE yarn_id=?",(yarn_id,))
        deleted=c.rowcount>0
        c.execute("DELETE FROM yarn_suppliers WHERE yarn_id=?",(yarn_id,))
        self.conn.commit()
        return deleted

    def add_supplier(self,yarn_id,name,price_amount,price_currency,product_url,notes,now):
        c=self.conn.cursor()
        c.execute("""INSERT INTO yarn_suppliers(yarn_id,name,price_amount,price_currency,product_url,notes,
                     created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",
                  (yarn_id,name,price_amount,price_currency,product_url,notes,now,now))
        self.conn.commit()
        r=self.conn.execute("SELECT * FROM yarn_suppliers WHERE id=?",(c.lastrowid,)).fetchone()
        return dict(r)

    def list_suppliers(self,yarn_id):
        rows=self.conn.execute("SELECT * FROM yarn_suppliers WHERE yarn_id=? ORDER BY price_amount IS NULL,price_amount,id",
                                (yarn_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_supplier(self,yarn_id,supplier_id):
        c=self.conn.cursor()
        c.execute("DELETE FROM yarn_suppliers WHERE id=? AND yarn_id=?",(supplier_id,yarn_id))
        self.conn.commit()
        return c.rowcount>0

    def get_setting(self,key,default=None):
        r=self.conn.execute("SELECT value FROM app_settings WHERE key=?",(key,)).fetchone()
        return r["value"] if r is not None else default

    def set_setting(self,key,value):
        self.conn.execute("INSERT INTO app_settings(key,value) VALUES(?,?) "
                           "ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,value))
        self.conn.commit()

    def all_settings(self):
        return {r["key"]:r["value"] for r in self.conn.execute("SELECT key,value FROM app_settings")}

    def upsert_stash(self,user_id,yarn_id,quantity_g,quantity_skeins,notes,now):
        existing=self.get_stash_entry(user_id,yarn_id)
        c=self.conn.cursor()
        if existing is None:
            c.execute("""INSERT INTO stash(user_id,yarn_id,quantity_g,quantity_skeins,notes,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?)""",
                      (user_id,yarn_id,quantity_g,quantity_skeins,notes,now,now))
        else:
            c.execute("""UPDATE stash SET quantity_g=?,quantity_skeins=?,notes=?,updated_at=? WHERE id=?""",
                      (quantity_g,quantity_skeins,notes,now,existing["id"]))
        self.conn.commit()
        return self.get_stash_entry(user_id,yarn_id)

    def list_stash(self,user_id):
        rows=self.conn.execute("SELECT * FROM stash WHERE user_id IS ? ORDER BY updated_at DESC",(user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_stash_entry(self,user_id,yarn_id):
        r=self.conn.execute("SELECT * FROM stash WHERE user_id IS ? AND yarn_id=?",(user_id,yarn_id)).fetchone()
        return dict(r) if r is not None else None

    def delete_stash(self,user_id,yarn_id):
        c=self.conn.cursor()
        c.execute("DELETE FROM stash WHERE user_id IS ? AND yarn_id=?",(user_id,yarn_id))
        self.conn.commit()
        return c.rowcount>0

    def upsert_pattern(self,pattern_dict,meta,checksum,now):
        c=self.conn.cursor()
        key=(pattern_dict["pattern_id"],pattern_dict["version"])
        c.execute("""
        INSERT INTO patterns(pattern_id,version,name,family_id,difficulty,tags_json,techniques_json,pattern_json,
        source_type,source_reference,license_id,checksum,active,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(pattern_id,version) DO UPDATE SET
          name=excluded.name,family_id=excluded.family_id,difficulty=excluded.difficulty,
          tags_json=excluded.tags_json,techniques_json=excluded.techniques_json,pattern_json=excluded.pattern_json,
          source_type=excluded.source_type,source_reference=excluded.source_reference,license_id=excluded.license_id,
          checksum=excluded.checksum,active=excluded.active,updated_at=excluded.updated_at
        """,(
          key[0],key[1],meta["name"],meta["family_id"],meta["difficulty"],
          json.dumps(meta.get("tags",[])),json.dumps(meta.get("techniques",[])),
          json.dumps(pattern_dict,sort_keys=True),meta.get("source_type","internal"),
          meta.get("source_reference"),meta.get("license_id"),checksum,1 if meta.get("active",True) else 0,now,now
        ))
        c.execute("DELETE FROM pattern_fts WHERE pattern_id=? AND version=?",key)
        c.execute("INSERT INTO pattern_fts(pattern_id,version,name,family_id,tags,techniques) VALUES(?,?,?,?,?,?)",
                  (key[0],key[1],meta["name"],meta["family_id"],
                   " ".join(meta.get("tags",[]))," ".join(meta.get("techniques",[]))))
        self.conn.commit()

    def audit(self,**kwargs):
        self.conn.execute("""INSERT INTO provenance_audit(entity_type,entity_id,version,source_type,source_reference,
        license_id,evidence_level,checksum,imported_at) VALUES(?,?,?,?,?,?,?,?,?)""",
        (kwargs.get("entity_type"),kwargs.get("entity_id"),kwargs.get("version"),kwargs.get("source_type"),
         kwargs.get("source_reference"),kwargs.get("license_id"),kwargs.get("evidence_level"),
         kwargs["checksum"],kwargs["imported_at"]))
        self.conn.commit()

    def quarantine(self,entity_type,source_file,raw_json,error_code,error_message,created_at):
        self.conn.execute("""INSERT INTO quarantine(entity_type,source_file,raw_json,error_code,error_message,created_at)
        VALUES(?,?,?,?,?,?)""",(entity_type,source_file,raw_json,error_code,error_message,created_at))
        self.conn.commit()

    def search_patterns(self,query,limit=20):
        return [dict(r) for r in self.conn.execute(
          """SELECT p.pattern_id,p.version,p.name,p.family_id,p.difficulty,p.tags_json,p.techniques_json
             FROM pattern_fts f JOIN patterns p ON p.pattern_id=f.pattern_id AND p.version=f.version
             WHERE pattern_fts MATCH ? AND p.active=1 LIMIT ?""",(query,limit))]

    def search_yarns(self,query,limit=20):
        return [dict(r) for r in self.conn.execute(
          """SELECT y.* FROM yarn_fts f JOIN yarns y ON y.yarn_id=f.yarn_id
             WHERE yarn_fts MATCH ? LIMIT ?""",(query,limit))]

    def create_product_line(self,name,description,photo_url,product_url,now):
        c=self.conn.cursor()
        try:
            c.execute("""INSERT INTO product_lines(name,description,photo_url,product_url,created_at,updated_at)
                         VALUES(?,?,?,?,?,?)""",(name,description,photo_url,product_url,now,now))
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise
        self.conn.commit()
        return self.get_product_line(c.lastrowid)

    def list_product_lines(self):
        rows=self.conn.execute("SELECT * FROM product_lines ORDER BY name").fetchall()
        return [self._with_materials(dict(r)) for r in rows]

    def get_product_line(self,line_id):
        r=self.conn.execute("SELECT * FROM product_lines WHERE id=?",(line_id,)).fetchone()
        return self._with_materials(dict(r)) if r is not None else None

    def _with_materials(self,line):
        mats=self.list_materials(line["id"])
        costs=[m["cost"] for m in mats if m.get("cost") is not None]
        currencies={m["price_currency"] for m in mats if m.get("price_currency")}
        line["materials"]=mats
        if mats and len(costs)==len(mats) and len(currencies)<=1:
            line["total_cost"]=round(sum(costs),2)
            line["total_cost_currency"]=next(iter(currencies),None)
        else:
            line["total_cost"]=None
            line["total_cost_currency"]=None
        return line

    def update_product_line(self,line_id,now,**fields):
        allowed={k:v for k,v in fields.items() if k in ("name","description","photo_url","product_url") and v is not None}
        if not allowed:
            return self.get_product_line(line_id)
        sets=",".join(f"{k}=?" for k in allowed)+",updated_at=?"
        vals=list(allowed.values())+[now,line_id]
        c=self.conn.cursor()
        try:
            c.execute(f"UPDATE product_lines SET {sets} WHERE id=?",vals)
        except sqlite3.IntegrityError:
            self.conn.rollback()
            raise
        self.conn.commit()
        return self.get_product_line(line_id) if c.rowcount>0 else None

    def delete_product_line(self,line_id):
        c=self.conn.cursor()
        c.execute("DELETE FROM product_lines WHERE id=?",(line_id,))
        deleted=c.rowcount>0
        c.execute("DELETE FROM product_line_materials WHERE product_line_id=?",(line_id,))
        self.conn.commit()
        return deleted

    def add_material(self,product_line_id,yarn_id,length_m,quantity_g,notes,now):
        c=self.conn.cursor()
        c.execute("""INSERT INTO product_line_materials(product_line_id,yarn_id,length_m,quantity_g,notes,created_at)
                     VALUES(?,?,?,?,?,?)""",(product_line_id,yarn_id,length_m,quantity_g,notes,now))
        self.conn.commit()
        r=self.conn.execute("SELECT * FROM product_line_materials WHERE id=?",(c.lastrowid,)).fetchone()
        return dict(r)

    def list_materials(self,product_line_id):
        rows=self.conn.execute(
            """SELECT m.*, y.brand as yarn_brand, y.product as yarn_product,
                      y.package_length_m, y.package_mass_g, y.price_amount, y.price_currency
               FROM product_line_materials m LEFT JOIN yarns y ON y.yarn_id=m.yarn_id
               WHERE m.product_line_id=? ORDER BY m.id""",(product_line_id,)).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            packages=None
            if d.get("length_m") and d.get("package_length_m"):
                packages=math.ceil(d["length_m"]/d["package_length_m"])
            elif d.get("quantity_g") and d.get("package_mass_g"):
                packages=math.ceil(d["quantity_g"]/d["package_mass_g"])
            d["packages"]=packages
            d["cost"]=round(packages*d["price_amount"],2) if (packages and d.get("price_amount")) else None
            out.append(d)
        return out

    def delete_material(self,product_line_id,material_id):
        c=self.conn.cursor()
        c.execute("DELETE FROM product_line_materials WHERE id=? AND product_line_id=?",
                   (material_id,product_line_id))
        self.conn.commit()
        return c.rowcount>0

    def counts(self):
        return {
          "yarns":self.conn.execute("SELECT COUNT(*) FROM yarns").fetchone()[0],
          "patterns":self.conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0],
          "quarantine":self.conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()[0],
          "audit":self.conn.execute("SELECT COUNT(*) FROM provenance_audit").fetchone()[0]
        }
