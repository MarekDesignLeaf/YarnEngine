# M8 Production Integrity & Master Alignment

Implemented after audit against Master Document v0.1.

1. Production promotion gate
Production promotion now requires at least four calibration samples, at least one calibrated operation and validation error evidence. A calibration snapshot may additionally block promotion when it explicitly reports undercovered operations. Every model stage transition is recorded in model_stage_history.

These are software governance minimums, not claims of scientific sufficiency. Real production acceptance thresholds still require empirical policy based on real data.

2. Runtime domain policy
calibrated mode now supports strict, warn and research domain policies. strict is the default and rejects predictions outside the calibrated domain. warn returns the prediction with explicit warnings. research permits exploratory use.

3. Project result integrity
Projects store SHA256 request_hash and result_request_hash. Changing a calculation request invalidates and clears the old result. A server-side project calculation endpoint calculates directly from the stored request and stores a matching result fingerprint.

4. Tier alignment
Measured swatch is Tier A. Approved operation calibration model is Tier B. Research geometry is labelled research_geometry rather than Tier C. Tier C remains reserved for future generic pattern-family fallback as defined by the Master Document.

5. Schema identity
Model records now include model_schema_version and feature_spec_version.

6. Gauge precision
Calculation API gauge values are now floats rather than integers.

Remaining work
Production-grade uncertainty intervals, real calibration data, empirical acceptance thresholds, large pattern library, generic Tier C fallback, multi-yarn/colourwork and further branch knitting remain incomplete.
