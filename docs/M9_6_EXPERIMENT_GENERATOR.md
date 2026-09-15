# M9.6 Calibration Experiment Generator

The Crochet Calibration workspace can now inspect stored physical evidence and generate only the measurements missing from the configured evidence gate.

The default core amigurumi set is SC, SC_INC, SC2TOG, SC_BLO, SC_FLO, SLST and CH. The required operations and evidence minima remain configurable.

The generator creates experiment IDs, replicate groups, operation targets, construction context and measurement fields. It deliberately leaves the physical operation count target unset: the operator chooses a practical sample size and records the exact executed count. This avoids inventing a universal sample size without experimental evidence.

The generated experiment plan can be printed on A4. Each experiment has a physical measurement table. Completed values are entered through the M9.5 calibration UI and become persistent calibration records.

This is an evidence acquisition planner, not calibration data and not a statistical sufficiency claim.
