import sqlite3
CURRENT_SCHEMA_VERSION=1
def ensure_version(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL)")
    row=conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version(version) VALUES(?)",(CURRENT_SCHEMA_VERSION,))
        conn.commit()
        return CURRENT_SCHEMA_VERSION
    if row[0]!=CURRENT_SCHEMA_VERSION:
        raise RuntimeError(f"unsupported schema version {row[0]}; expected {CURRENT_SCHEMA_VERSION}")
    return row[0]
