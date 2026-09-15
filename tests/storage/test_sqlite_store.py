from pathlib import Path
from src.storage.sqlite_store import SQLiteStore
from src.storage.migrations import ensure_version
def test_init_counts(tmp_path):
    s=SQLiteStore(tmp_path/"x.sqlite")
    try:
        assert ensure_version(s.conn)==1
        assert s.counts()["yarns"]==0
    finally:s.close()
