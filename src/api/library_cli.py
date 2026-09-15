import argparse,json
from pathlib import Path
from src.library.loader import load_library
from src.library.search import search_yarns,search_patterns
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=".")
    sub=p.add_subparsers(dest="cmd",required=True)
    y=sub.add_parser("yarns"); y.add_argument("--text"); y.add_argument("--weight",type=int)
    q=sub.add_parser("patterns"); q.add_argument("--text"); q.add_argument("--family")
    a=p.parse_args(); r=load_library(Path(a.root))
    if a.cmd=="yarns":
        out=[x.__dict__ for x in search_yarns(r,text=a.text,cyc_weight=a.weight)]
    else:
        out=[x.__dict__ for x in search_patterns(r,text=a.text,family_id=a.family)]
    print(json.dumps(out,indent=2))
if __name__=="__main__": main()
