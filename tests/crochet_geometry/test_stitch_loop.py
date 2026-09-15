import pytest
from src.crochet_geometry.stitch_loop import (
    operation_length_mm, program_length_mm, OPERATION_WRAP_RATIO,
    MEASURED_ANCHOR_OPERATIONS, HIGH_UNCERTAINTY_OPERATIONS,
)

def test_sc_is_the_measured_anchor_with_unit_ratio():
    assert OPERATION_WRAP_RATIO["SC"] == 1.0
    assert "SC" in MEASURED_ANCHOR_OPERATIONS

def test_taller_stitches_use_more_yarn_than_sc():
    sc = operation_length_mm("SC", 4.0, 4.0, 2.0)
    hdc = operation_length_mm("HDC", 4.0, 4.0, 2.0)
    dc = operation_length_mm("DC", 4.0, 4.0, 2.0)
    tr = operation_length_mm("TR", 4.0, 4.0, 2.0)
    dtr = operation_length_mm("DTR", 4.0, 4.0, 2.0)
    assert sc.length_mm < hdc.length_mm < dc.length_mm < tr.length_mm < dtr.length_mm

def test_increase_uses_about_twice_its_base_stitch():
    sc = operation_length_mm("SC", 4.0, 4.0, 2.0)
    sc_inc = operation_length_mm("SC_INC", 4.0, 4.0, 2.0)
    assert sc_inc.length_mm == pytest.approx(2 * sc.length_mm, rel=1e-6)

def test_ntog_decrease_uses_less_than_n_separate_stitches():
    sc = operation_length_mm("SC", 4.0, 4.0, 2.0)
    sc2tog = operation_length_mm("SC2TOG", 4.0, 4.0, 2.0)
    # shares one closing pull-through, so strictly less than 2 full single crochets
    assert sc.length_mm < sc2tog.length_mm < 2 * sc.length_mm

def test_measured_anchor_has_narrower_band_than_extrapolated_stitch():
    sc = operation_length_mm("SC", 4.0, 4.0, 2.0)
    dc = operation_length_mm("DC", 4.0, 4.0, 2.0)
    sc_rel = (sc.upper_mm - sc.lower_mm) / sc.length_mm
    dc_rel = (dc.upper_mm - dc.lower_mm) / dc.length_mm
    assert sc_rel < dc_rel

def test_texture_stitches_carry_widest_band():
    puff = operation_length_mm("PUFF3", 4.0, 4.0, 2.0)
    dc = operation_length_mm("DC", 4.0, 4.0, 2.0)
    assert puff.operation_id in HIGH_UNCERTAINTY_OPERATIONS
    puff_rel = (puff.upper_mm - puff.lower_mm) / puff.length_mm
    dc_rel = (dc.upper_mm - dc.lower_mm) / dc.length_mm
    assert puff_rel > dc_rel

def test_unknown_operation_raises():
    with pytest.raises(KeyError):
        operation_length_mm("NOT_A_STITCH", 4.0, 4.0, 2.0)

def test_program_length_mm_sums_and_scales_with_count():
    total1, lower1, upper1, warnings, unsupported = program_length_mm({"SC": 1}, 4.0, 4.0, 2.0)
    total10, *_ = program_length_mm({"SC": 10}, 4.0, 4.0, 2.0)
    assert total10 == pytest.approx(10 * total1, rel=1e-9)
    assert lower1 < total1 < upper1
    assert not unsupported
    assert any("Storck" in w for w in warnings)

def test_program_length_mm_reports_unsupported_operations_without_crashing():
    total, lower, upper, warnings, unsupported = program_length_mm({"SC": 5, "NOT_A_STITCH": 3}, 4.0, 4.0, 2.0)
    assert total > 0
    assert unsupported == ("NOT_A_STITCH",)
    assert any("NOT_A_STITCH" in w for w in warnings)

def test_program_length_mm_zero_when_all_operations_unsupported():
    total, lower, upper, warnings, unsupported = program_length_mm({"NOT_A_STITCH": 3}, 4.0, 4.0, 2.0)
    assert total == 0
    assert unsupported == ("NOT_A_STITCH",)

def test_program_length_mm_ignores_non_positive_counts():
    total, *_ = program_length_mm({"SC": 5, "DC": 0, "TR": -1}, 4.0, 4.0, 2.0)
    sc_only, *_ = program_length_mm({"SC": 5}, 4.0, 4.0, 2.0)
    assert total == pytest.approx(sc_only, rel=1e-9)
