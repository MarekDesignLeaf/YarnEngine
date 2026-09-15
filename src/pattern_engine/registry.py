import json
from pathlib import Path

def load_operation_registry(path) -> dict[str, dict]:
    raw=json.loads(Path(path).read_text(encoding="utf-8"))
    return {x["operation_id"]:x for x in raw}
