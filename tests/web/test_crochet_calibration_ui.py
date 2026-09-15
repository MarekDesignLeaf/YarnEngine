from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_crochet_calibration_ui_and_print_form_present():
 h=(ROOT/"src/web/static/index.html").read_text()
 j=(ROOT/"src/web/static/app.js").read_text()
 assert 'id="crochetCalibrationPanel"' in h
 assert 'id="printCrochetForm"' in h
 assert "Crochet Calibration Measurement Form" in j
 assert "/api/crochet/calibration/records" in j
 assert "/api/crochet/calibration/fit-register" in j
