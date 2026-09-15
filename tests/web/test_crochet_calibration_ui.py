from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_calculator_ui_exposes_login_calculator_library_and_calibration():
 h=(ROOT/"src/web/static/index.html").read_text(encoding="utf-8")
 for needle in ('id="viewLogin"','id="btnCalc"','id="gallery"','id="swLen"','id="rounds"','id="tab-admin"','/api/patterns/full','/api/complex-consumption/calculate'):
  assert needle in h
