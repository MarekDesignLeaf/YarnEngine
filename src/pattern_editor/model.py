from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class EditorCell:
    row:int
    col:int
    operation_id:str
    span:int=1

    def __post_init__(self):
        if self.row<1 or self.col<1: raise ValueError("row/col must be >= 1")
        if not self.operation_id: raise ValueError("operation_id required")
        if self.span<1: raise ValueError("span must be >= 1")

@dataclass(frozen=True)
class EditorPattern:
    pattern_id:str
    version:str
    name:str
    width:int
    height:int
    cells:tuple[EditorCell,...]

    def __post_init__(self):
        if not self.pattern_id or not self.version or not self.name:
            raise ValueError("identity fields required")
        if self.width<1 or self.height<1: raise ValueError("width/height must be >= 1")
