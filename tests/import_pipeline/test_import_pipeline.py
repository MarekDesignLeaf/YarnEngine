from pathlib import Path
import json
from src.storage.sqlite_store import SQLiteStore
from src.import_pipeline.core import import_yarn_file
from src.import_pipeline.bulk import bulk_import_patterns
from src.pattern_engine.registry import load_operation_registry
ROOT=Path(__file__).resolve().parents[2]

def test_yarn_import_and_fts(tmp_path):
    s=SQLiteStore(tmp_path/"x.sqlite")
    try:
        r=import_yarn_file(s,ROOT/"data/yarns/TEST_Y1.json")
        assert r["status"]=="imported"
        assert s.counts()["yarns"]==1
        found=s.search_yarns("Medium")
        assert found and found[0]["yarn_id"]=="TEST_Y1"
    finally:s.close()

def test_bad_yarn_quarantine(tmp_path):
    s=SQLiteStore(tmp_path/"x.sqlite")
    try:
        r=import_yarn_file(s,ROOT/"data/import_examples/bad_yarn.json")
        assert r["status"]=="quarantined"
        assert s.counts()["quarantine"]==1
    finally:s.close()

def test_bulk_patterns_and_fts(tmp_path):
    s=SQLiteStore(tmp_path/"x.sqlite")
    try:
        ops=load_operation_registry(ROOT/"data/stitches/operations.seed.json")
        r=bulk_import_patterns(s,ROOT/"data/patterns",ROOT/"data/library/pattern_metadata.json",ops)
        assert any(x["status"]=="imported" for x in r)
        f=s.search_patterns("Cable")
        assert any(x["pattern_id"]=="CABLE_2X2_SIMPLE" for x in f)
    finally:s.close()
