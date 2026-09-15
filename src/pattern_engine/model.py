from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class Token:
    op: str
    n: int = 1

    def __post_init__(self):
        if not self.op:
            raise ValueError("operation id cannot be empty")
        if self.n <= 0:
            raise ValueError("token count must be > 0")

@dataclass(frozen=True)
class PatternRow:
    row: int
    side: str
    sequence: tuple[Token, ...]

    def __post_init__(self):
        if self.row <= 0:
            raise ValueError("row number must be > 0")
        if self.side not in {"RS","WS","ROUND","NA"}:
            raise ValueError("invalid side")
        if not self.sequence:
            raise ValueError("row sequence cannot be empty")

@dataclass(frozen=True)
class PatternDefinition:
    pattern_id: str
    version: str
    name: str
    repeat_width_stitches: int
    repeat_height_rows: int
    rows: tuple[PatternRow, ...]

    def __post_init__(self):
        if self.repeat_width_stitches <= 0 or self.repeat_height_rows <= 0:
            raise ValueError("repeat dimensions must be > 0")
        if len(self.rows) != self.repeat_height_rows:
            raise ValueError("row count must equal repeat height")
