from pathlib import Path
from src.storage.sqlite_store import SQLiteStore
from src.storage.migrations import ensure_version
from src.import_pipeline.bulk import bulk_import_yarns, bulk_import_patterns
from src.pattern_engine.registry import load_operation_registry


def ensure_demo_database(root: Path, db_path: Path) -> None:
    store = SQLiteStore(db_path)
    try:
        ensure_version(store.conn)
        operations = load_operation_registry(root / "data/stitches/operations.seed.json")
        # Always synchronize bundled canonical libraries. Imports are
        # checksum/version aware and use upsert semantics, so verified yarns
        # added to the repository become available without deleting user data.
        bulk_import_patterns(
            store,
            root / "data/patterns",
            root / "data/library/pattern_metadata.json",
            operations,
        )
        bulk_import_yarns(store, root / "data/yarns")
    finally:
        store.close()
