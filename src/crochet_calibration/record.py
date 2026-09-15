from dataclasses import dataclass
from typing import Mapping
from src.crochet.amigurumi import CROCHET_OPS

@dataclass(frozen=True)
class CrochetCalibrationRecord:
    record_id:str
    replicate_group_id:str
    crocheter_id:str
    yarn_id:str
    hook_mm:float
    gauge_stitches:int
    gauge_rows:int
    gauge_width_mm:float
    gauge_height_mm:float
    operation_counts:Mapping[str,int]
    yarn_length_m:float
    yarn_mass_g:float|None=None
    tex:float|None=None
    yarn_diameter_mm:float|None=None
    construction:str="flat"
    tension_condition:str="as_crocheted"
    evidence_reference:str|None=None

    def __post_init__(self):
        if not self.record_id or not self.replicate_group_id or not self.crocheter_id or not self.yarn_id:
            raise ValueError("record, replicate group, crocheter and yarn identifiers are required")
        if self.hook_mm<=0 or self.yarn_length_m<=0:raise ValueError("hook and yarn length must be positive")
        if min(self.gauge_stitches,self.gauge_rows,self.gauge_width_mm,self.gauge_height_mm)<=0:
            raise ValueError("gauge values must be positive")
        if self.construction not in {"flat","round","spiral"}:raise ValueError("invalid crochet construction")
        if not self.operation_counts:raise ValueError("operation counts required")
        bad=[op for op,n in self.operation_counts.items() if op not in CROCHET_OPS or int(n)<0]
        if bad:raise ValueError("invalid crochet operations: "+",".join(bad))

    @property
    def wale_spacing_mm(self):return self.gauge_width_mm/self.gauge_stitches
    @property
    def course_spacing_mm(self):return self.gauge_height_mm/self.gauge_rows
