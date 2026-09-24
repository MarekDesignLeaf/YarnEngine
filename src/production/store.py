"""Production orders: a product moves through the steps the owner defines.

Nothing about the steps is assumed. The list of steps is owner data; each order
keeps its own copy of the steps it was started with, so editing the list later
never rewrites the history of orders already in production. Every change to an
order is recorded as an event (who, when, from which step to which, why).
"""
import sqlite3, json, datetime
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS stages(
  position INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS orders(
  order_id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_line_id INTEGER,
  product_name TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity>0),
  note TEXT,
  stages_json TEXT NOT NULL,
  stage_index INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','done','cancelled')),
  created_by INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, updated_at DESC);
CREATE TABLE IF NOT EXISTS order_events(
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  at TEXT NOT NULL,
  user_id INTEGER,
  username TEXT,
  action TEXT NOT NULL,
  from_stage TEXT,
  to_stage TEXT,
  note TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_order ON order_events(order_id, event_id);
"""

MAX_STAGES = 30
MAX_NAME = 80


class ProductionError(ValueError):
    """A request that breaks a production rule (shown to the user as is)."""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ProductionStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # ---------------------------------------------------------------- steps
    def stages(self):
        return [r["name"] for r in self.conn.execute("SELECT name FROM stages ORDER BY position")]

    def set_stages(self, names):
        clean = [str(n).strip() for n in names if str(n).strip()]
        if len(clean) > MAX_STAGES:
            raise ProductionError(f"at most {MAX_STAGES} steps")
        if any(len(n) > MAX_NAME for n in clean):
            raise ProductionError(f"a step name can be at most {MAX_NAME} characters")
        if len({n.lower() for n in clean}) != len(clean):
            raise ProductionError("two steps have the same name")
        with self.conn:
            self.conn.execute("DELETE FROM stages")
            self.conn.executemany("INSERT INTO stages(position,name) VALUES(?,?)", list(enumerate(clean)))
        return self.stages()

    # --------------------------------------------------------------- orders
    def _row(self, row):
        if row is None:
            return None
        d = dict(row)
        d["stages"] = json.loads(d.pop("stages_json"))
        n = len(d["stages"])
        d["current_stage"] = d["stages"][d["stage_index"]] if d["status"] == "open" else None
        d["steps_done"] = n if d["status"] == "done" else d["stage_index"]
        d["steps_total"] = n
        return d

    def get(self, order_id, with_events=False):
        d = self._row(self.conn.execute("SELECT * FROM orders WHERE order_id=?", (order_id,)).fetchone())
        if d is not None and with_events:
            d["events"] = [dict(r) for r in self.conn.execute(
                "SELECT * FROM order_events WHERE order_id=? ORDER BY event_id", (order_id,))]
        return d

    def list(self, status=None):
        if status:
            rows = self.conn.execute("SELECT * FROM orders WHERE status=? ORDER BY updated_at DESC", (status,))
        else:
            rows = self.conn.execute("SELECT * FROM orders ORDER BY status='open' DESC, updated_at DESC")
        return [self._row(r) for r in rows]

    def _event(self, order_id, user, action, from_stage=None, to_stage=None, note=None, at=None):
        self.conn.execute(
            "INSERT INTO order_events(order_id,at,user_id,username,action,from_stage,to_stage,note) VALUES(?,?,?,?,?,?,?,?)",
            (order_id, at or utc_now(), (user or {}).get("id"), (user or {}).get("username"),
             action, from_stage, to_stage, (note or "").strip() or None))

    def create(self, product_name, quantity, user=None, product_line_id=None, note=None):
        stages = self.stages()
        if not stages:
            raise ProductionError("define the production steps first")
        name = str(product_name or "").strip()
        if not name:
            raise ProductionError("product name is required")
        if not isinstance(quantity, int) or quantity < 1:
            raise ProductionError("quantity must be a whole number of at least 1")
        now = utc_now()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO orders(product_line_id,product_name,quantity,note,stages_json,stage_index,status,created_by,created_at,updated_at)"
                " VALUES(?,?,?,?,?,0,'open',?,?,?)",
                (product_line_id, name, quantity, (note or "").strip() or None,
                 json.dumps(stages, ensure_ascii=False), (user or {}).get("id"), now, now))
            oid = cur.lastrowid
            self._event(oid, user, "created", None, stages[0], note, at=now)
        return self.get(oid, with_events=True)

    def _open_or_raise(self, order_id):
        d = self.get(order_id)
        if d is None:
            raise KeyError(order_id)
        return d

    def advance(self, order_id, user=None, note=None):
        d = self._open_or_raise(order_id)
        if d["status"] != "open":
            raise ProductionError(f"order is {d['status']}")
        last = d["stage_index"] >= d["steps_total"] - 1
        now = utc_now()
        with self.conn:
            if last:
                self.conn.execute("UPDATE orders SET status='done',updated_at=? WHERE order_id=?", (now, order_id))
                self._event(order_id, user, "completed", d["current_stage"], None, note, at=now)
            else:
                nxt = d["stages"][d["stage_index"] + 1]
                self.conn.execute("UPDATE orders SET stage_index=stage_index+1,updated_at=? WHERE order_id=?", (now, order_id))
                self._event(order_id, user, "advanced", d["current_stage"], nxt, note, at=now)
        return self.get(order_id, with_events=True)

    def step_back(self, order_id, user=None, note=None):
        """Undo the last move: reopen a completed order at its last step, or go back one step."""
        d = self._open_or_raise(order_id)
        if d["status"] == "cancelled":
            raise ProductionError("order is cancelled")
        now = utc_now()
        with self.conn:
            if d["status"] == "done":
                last = d["stages"][-1]
                self.conn.execute("UPDATE orders SET status='open',stage_index=?,updated_at=? WHERE order_id=?",
                                  (d["steps_total"] - 1, now, order_id))
                self._event(order_id, user, "reopened", None, last, note, at=now)
            else:
                if d["stage_index"] == 0:
                    raise ProductionError("order is already at the first step")
                prev = d["stages"][d["stage_index"] - 1]
                self.conn.execute("UPDATE orders SET stage_index=stage_index-1,updated_at=? WHERE order_id=?", (now, order_id))
                self._event(order_id, user, "stepped_back", d["current_stage"], prev, note, at=now)
        return self.get(order_id, with_events=True)

    def cancel(self, order_id, user=None, reason=None):
        d = self._open_or_raise(order_id)
        if d["status"] != "open":
            raise ProductionError(f"order is {d['status']}")
        if not (reason or "").strip():
            raise ProductionError("a reason is required to cancel an order")
        now = utc_now()
        with self.conn:
            self.conn.execute("UPDATE orders SET status='cancelled',updated_at=? WHERE order_id=?", (now, order_id))
            self._event(order_id, user, "cancelled", d["current_stage"], None, reason, at=now)
        return self.get(order_id, with_events=True)
