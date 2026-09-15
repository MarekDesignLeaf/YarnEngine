from dataclasses import dataclass
from src.gauge_engine.gauge import project_grid
from src.project_geometry.model import EdgeZone,PartialRepeatMode
from src.project_geometry.expand import expand_project
@dataclass(frozen=True)
class ProjectPatternPlan:
    stitches:int; rows:int; achieved_width_mm:float; achieved_height_mm:float
    horizontal_layout:object; vertical_layout:object; operation_counts:dict; row_operation_counts:tuple
def create_project_pattern_plan(*,width_mm,height_mm,gauge,pattern,operations,edges=EdgeZone(),partial_mode=PartialRepeatMode.REJECT):
    g=project_grid(width_mm,height_mm,gauge)
    x=expand_project(pattern,operations,g.stitches,g.rows,edges,partial_mode)
    return ProjectPatternPlan(g.stitches,g.rows,g.achieved_width_mm,g.achieved_height_mm,x["horizontal_layout"],x["vertical_layout"],x["operation_counts"],x["row_operation_counts"])
