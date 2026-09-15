from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class YarnRecord:
    yarn_id:str
    brand:str
    product:str
    variant:str|None
    cyc_weight:int|None
    package_mass_g:float
    package_length_m:float
    fibre_composition:Mapping[str,float]
    tex:float|None=None
    nominal_diameter_mm:float|None=None
    wpi:float|None=None
    recommended_needle_min_mm:float|None=None
    recommended_needle_max_mm:float|None=None
    source_type:str="user"
    source_reference:str|None=None
    evidence_level:str="declared"

    def __post_init__(self):
        if not self.yarn_id or not self.brand or not self.product:
            raise ValueError("yarn_id, brand and product required")
        if self.cyc_weight is not None and not 0<=self.cyc_weight<=7:
            raise ValueError("cyc_weight must be 0..7")
        if self.package_mass_g<=0 or self.package_length_m<=0:
            raise ValueError("package mass and length must be > 0")
        if self.tex is not None and self.tex<=0: raise ValueError("tex must be > 0")
        if self.nominal_diameter_mm is not None and self.nominal_diameter_mm<=0:
            raise ValueError("diameter must be > 0")
        total=sum(self.fibre_composition.values())
        if abs(total-100.0)>0.05:
            raise ValueError("fibre composition must total 100%")

    @property
    def derived_tex(self):
        return self.package_mass_g/self.package_length_m*1000.0
