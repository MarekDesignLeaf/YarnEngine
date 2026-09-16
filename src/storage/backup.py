"""On-demand backup of every SQLite database under the app's data directory.

Uses sqlite3's own online backup API (Connection.backup()) rather than a raw
file copy, so a database that is actively being written to by a live request
is never copied mid-write into a corrupt snapshot -- this is exactly the API
SQLite provides for taking a consistent "hot backup" of a database that other
connections may be using concurrently.
"""
import io
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def build_backup_zip(data_dir: Path) -> bytes:
    """Return an in-memory zip containing a consistent snapshot of every
    *.sqlite file found directly under data_dir."""
    data_dir = Path(data_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for db_file in sorted(data_dir.glob("*.sqlite")):
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp) / db_file.name
                src_conn = sqlite3.connect(str(db_file))
                dst_conn = sqlite3.connect(str(tmp_path))
                try:
                    src_conn.backup(dst_conn)
                finally:
                    dst_conn.close()
                    src_conn.close()
                zf.write(tmp_path, arcname=db_file.name)
    return buf.getvalue()
