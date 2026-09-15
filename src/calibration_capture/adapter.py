from src.calibration.dataset import CalibrationSample

def to_calibration_sample(record):
    return CalibrationSample(
        calibration_id=record.record_id,
        pattern_id=record.pattern_id,
        operation_counts=record.operation_counts,
        yarn_length_m=record.yarn_length_m,
        wale_spacing_mm=record.wale_spacing_mm,
        course_spacing_mm=record.course_spacing_mm,
        yarn_diameter_mm=record.yarn_diameter_mm,
        tex=record.tex
    )
