from dataclasses import dataclass
from .dataset import CalibrationSample

@dataclass(frozen=True)
class FeatureSpec:
    operation_ids: tuple[str,...]
    include_intercept: bool = True
    include_wale: bool = True
    include_course: bool = True
    include_diameter: bool = True

def build_feature_spec(samples) -> FeatureSpec:
    ops=sorted({op for s in samples for op in s.operation_counts})
    return FeatureSpec(tuple(ops))

def sample_feature_vector(sample: CalibrationSample, spec: FeatureSpec) -> list[float]:
    total=max(1,sum(sample.operation_counts.values()))
    out=[]
    if spec.include_intercept:
        out.append(1.0)
    # Counts are normalized by 1000 operation occurrences to improve numeric scale.
    for op in spec.operation_ids:
        out.append(sample.operation_counts.get(op,0)/1000.0)
    if spec.include_wale:
        out.append(sample.wale_spacing_mm)
    if spec.include_course:
        out.append(sample.course_spacing_mm)
    if spec.include_diameter:
        out.append(sample.yarn_diameter_mm if sample.yarn_diameter_mm is not None else 0.0)
    return out

def feature_names(spec: FeatureSpec) -> list[str]:
    names=[]
    if spec.include_intercept: names.append("intercept")
    names += [f"op:{op}/1000" for op in spec.operation_ids]
    if spec.include_wale: names.append("wale_spacing_mm")
    if spec.include_course: names.append("course_spacing_mm")
    if spec.include_diameter: names.append("yarn_diameter_mm")
    return names
