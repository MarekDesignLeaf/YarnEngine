from dataclasses import dataclass
from enum import Enum

class PartialRepeatMode(str, Enum):
    REJECT="reject"; LEFT="left"; RIGHT="right"; SPLIT="split"; CENTER="center"

@dataclass(frozen=True)
class EdgeZone:
    left_stitches:int=0
    right_stitches:int=0
    left_operation:str="K"
    right_operation:str="K"
    def __post_init__(self):
        if self.left_stitches<0 or self.right_stitches<0: raise ValueError("edge counts must be >= 0")

@dataclass(frozen=True)
class HorizontalLayout:
    total_stitches:int; edge_left:int; repeat_width:int; full_repeats:int
    partial_left:int; partial_right:int; edge_right:int; mode:str
    @property
    def accounted_stitches(self):
        return self.edge_left+self.partial_left+self.full_repeats*self.repeat_width+self.partial_right+self.edge_right

@dataclass(frozen=True)
class VerticalLayout:
    total_rows:int; repeat_height:int; full_repeats:int; partial_rows:int
    @property
    def accounted_rows(self): return self.full_repeats*self.repeat_height+self.partial_rows
