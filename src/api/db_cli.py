import argparse,json
from pathlib import Path
from src.storage.sqlite_store import SQLiteStore
from src.storage.migrations import ensure_version
from src.pattern_engine.registry import load_operation_registry
from src.import_pipeline.bulk import bulk_import_yarns,bulk_import_patterns

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",default="data/db/yarn_engine.sqlite")
    sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("init")
    sub.add_parser("import-all")
    sp=sub.add_parser("search-patterns"); sp.add_argument("query")
    sy=sub.add_parser("search-yarns"); sy.add_argument("query")
    a=p.parse_args()
    store=SQLiteStore(a.db); ensure_version(store.conn)
    try:
        if a.cmd=="init":
            out=store.counts()
        elif a.cmd=="import-all":
            ops=load_operation_registry("data/stitches/operations.seed.json")
            yr=bulk_import_yarns(store,"data/yarns")
            pr=bulk_import_patterns(store,"data/patterns","data/library/pattern_metadata.json",ops)
            out={"yarns":yr,"patterns":pr,"counts":store.counts()}
        elif a.cmd=="search-patterns":
            out=store.search_patterns(a.query)
        else:
            out=store.search_yarns(a.query)
        print(json.dumps(out,indent=2,default=str))
    finally:
        store.close()
if __name__=="__main__": main()
