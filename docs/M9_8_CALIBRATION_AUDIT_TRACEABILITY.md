# M9.8 Calibration Audit & Traceability

M9.8 makes the physical calibration dataset traceable.

Every calibration dataset snapshot is canonicalized by record ID and hashed with SHA256. Changing a measured value changes the dataset hash. Model registration stores the exact dataset SHA256 together with record IDs, coverage, evidence gate, replicate quality and measurement consistency.

The calibration audit endpoint returns the current dataset identity, readiness, QC state and a second audit SHA256 over the audit payload. The UI can print an A4 Calibration Audit containing dataset identity and QC results.

This does not make a measurement correct. It makes the exact evidence used for a calibration identifiable and detects later changes to that evidence.
