# M9.5 Printable Measurement & Calibration Workflow

The web application now provides a Crochet Calibration workspace intended for real workshop use.

Workflow:
1. Enter form ID, operator/crocheter, yarn ID, hook size, construction and replicate group.
2. Select Generate & print measurement form.
3. The browser creates an A4 print layout and opens the print dialog.
4. The physical sheet contains fields for gauge counts, measured dimensions, yarn length, yarn mass, yarn diameter, evidence reference and canonical operation counts.
5. After the physical sample is measured, enter the completed values in the same Crochet Calibration workspace.
6. Save measured record. It is persisted in the crochet calibration SQLite database.
7. Calibration status reports missing evidence.
8. Fit & register is blocked until the evidence gate passes.
9. A fitted model is registered as research; it is not automatically promoted to production.

The printed sheet deliberately tells the operator not to estimate missing measurements.

No OCR is used in M9.5. The completed paper form is transcribed into the application manually, which avoids introducing unverified OCR measurement values into calibration evidence.
