# M9.7 Measurement Quality Gate

M9.7 adds quality control before crochet calibration fitting.

Replicate repeatability is evaluated within replicate groups using the coefficient of variation of measured yarn length. Default project gates are warning above 10 percent and failure above 20 percent with at least three replicates. These thresholds are configurable internal QC gates and are not claimed as universal crochet standards.

When yarn mass and tex are both supplied, the engine independently derives length from mass and tex and compares it with the directly measured yarn length. The default mismatch tolerance is 15 percent and is configurable.

A failed replicate QC group or failed mass/tex consistency blocks fit-register. The raw measurement is retained; the software does not silently repair or replace it.

The Crochet Calibration UI now exposes Check measurement quality before fitting.
