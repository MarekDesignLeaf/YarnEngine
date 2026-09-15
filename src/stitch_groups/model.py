
from dataclasses import dataclass, field

@dataclass(frozen=True)
class StitchGroup:
    group_id:str
    stitches:int
    state:str="active"  # active|held|closed
    parent_ids:tuple[str,...]=()
    def __post_init__(self):
        if not self.group_id:
            raise ValueError("group_id required")
        if self.stitches < 0:
            raise ValueError("stitches cannot be negative")
        if self.state not in {"active","held","closed"}:
            raise ValueError("invalid group state")

@dataclass(frozen=True)
class GroupEvent:
    step:int
    action:str
    source_ids:tuple[str,...]=()
    target_ids:tuple[str,...]=()
    counts:tuple[int,...]=()
    note:str|None=None
    def __post_init__(self):
        if self.step<=0:
            raise ValueError("step must be > 0")
        if self.action not in {"hold","resume","split","join","close"}:
            raise ValueError("invalid group action")
