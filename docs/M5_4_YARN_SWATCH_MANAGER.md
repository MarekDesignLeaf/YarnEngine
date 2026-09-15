# M5.4 Yarn & Swatch Manager

M5.4 introduces user-entered yarns and persistent empirical swatches.

User yarns are marked `source_type=user_created` and `evidence_level=user_declared`.
They are never confused with published or independently measured data.

Measured swatches reference an exact pattern version and yarn ID. A swatch stores stitch count,
row count, physical dimensions, optional needle diameter, measured yarn length and/or mass, notes,
and timestamps.

The web UI can reuse a saved swatch directly in Tier A measured-swatch calculation.

This is the foundation for production calibration datasets. Saving a swatch does not automatically
declare it calibration-grade: replicate measurement, evidence capture and grouped validation remain
separate quality controls.
