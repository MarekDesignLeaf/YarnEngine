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


SECRET_SETTING_PREFIX = "secret."


def _strip_secrets(db_path: Path) -> None:
    """Remove credentials from a backup copy.

    A backup gets emailed, copied to a USB stick and kept for years. Settings
    whose key starts with "secret." (an API key typed into the admin page, for
    instance) are dropped from the snapshot, so a leaked backup cannot be used
    to spend someone's money. Restoring a backup therefore means re-entering
    those keys, which is the safer way round.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        has_settings = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'").fetchone()
        if has_settings:
            conn.execute("DELETE FROM settings WHERE key LIKE ?", (SECRET_SETTING_PREFIX + "%",))
            conn.commit()
    finally:
        conn.close()


def build_backup_zip(data_dir: Path) -> bytes:
    """Return an in-memory zip containing a consistent snapshot of every
    *.sqlite file found directly under data_dir, with credentials removed."""
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
                _strip_secrets(tmp_path)
                zf.write(tmp_path, arcname=db_file.name)
    return buf.getvalue()
