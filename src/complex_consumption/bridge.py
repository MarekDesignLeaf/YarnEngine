from src.production_model.runtime import calculate_with_production_model

def calculate_operation_program(*,record,operation_counts,gauge,yarn_diameter_mm,allowance_percent=0.0,
                                tex=None,package_length_m=None,domain_policy="strict",source="operation_program"):
    """Consumption bridge for shaped, branch and amigurumi programs.
    Uses actual aggregated canonical operation counts instead of rectangular repeat expansion."""
    if not operation_counts or sum(int(v) for v in operation_counts.values())<=0:
        raise ValueError("operation program contains no yarn-consuming operations")
    # Width/height are not used to derive counts here. They are retained as a neutral grid carrier
    # for the legacy result envelope; operation counts are authoritative.
    calc,pred=calculate_with_production_model(
        record=record,operation_counts=operation_counts,gauge=gauge,
        width_mm=100.0,height_mm=100.0,yarn_diameter_mm=yarn_diameter_mm,
        allowance_percent=allowance_percent,tex=tex,package_length_m=package_length_m,
        domain_policy=domain_policy)
    return calc,pred,{"source":source,"operation_counts":dict(operation_counts),
                      "count_basis":"executed canonical operation program",
                      "rectangular_area_used_for_operation_counts":False}
