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
    """Return consistent SQLite snapshots plus all approved persistent media assets.

    Never include the session-signing secret or SQLite journal/WAL files. The
    database snapshots are already consistent due to sqlite3.Connection.backup.
    """
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
        # Database-only backups silently lost user photos and generated catalogues.
        # Keep paths relative so an operator can restore them onto a fresh volume.
        for directory in ("product_photos", "catalogue_output"):
            media_root = data_dir / directory
            if not media_root.is_dir() or media_root.is_symlink():
                continue
            for source in sorted(media_root.rglob("*")):
                if not source.is_file() or source.is_symlink():
                    continue
                relative = source.relative_to(data_dir)
                if (source.name.startswith(".") or source.name.endswith(
                        (".tmp", ".sqlite", ".sqlite-wal", ".sqlite-shm", ".sqlite-journal"))):
                    continue
                zf.write(source, arcname=relative.as_posix())
    return buf.getvalue()
