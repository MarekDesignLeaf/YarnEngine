
from dataclasses import dataclass

@dataclass(frozen=True)
class ShapingToken:
    op: str
    n: int = 1
    def __post_init__(self):
        if not self.op:
            raise ValueError("operation id cannot be empty")
        if self.n <= 0:
            raise ValueError("token count must be > 0")

@dataclass(frozen=True)
class ShapingRow:
    row: int
    side: str
    sequence: tuple[ShapingToken,...]
    expected_in: int | None = None
    expected_out: int | None = None
    def __post_init__(self):
        if self.row <= 0:
            raise ValueError("row number must be > 0")
        if self.side not in {"RS","WS","ROUND","NA"}:
            raise ValueError("invalid side")
        if not self.sequence:
            raise ValueError("row sequence cannot be empty")
        if self.expected_in is not None and self.expected_in < 0:
            raise ValueError("expected_in cannot be negative")
        if self.expected_out is not None and self.expected_out < 0:
            raise ValueError("expected_out cannot be negative")

@dataclass(frozen=True)
class ShapedPatternDefinition:
    pattern_id: str
    version: str
    name: str
    initial_stitches: int
    rows: tuple[ShapingRow,...]
    construction: str = "flat"
    def __post_init__(self):
        if not self.pattern_id or not self.version or not self.name:
            raise ValueError("pattern identity fields are required")
        if self.initial_stitches <= 0:
            raise ValueError("initial_stitches must be > 0")
        if not self.rows:
            raise ValueError("at least one shaping row is required")
        if self.construction not in {"flat","round"}:
            raise ValueError("construction must be flat or round")
