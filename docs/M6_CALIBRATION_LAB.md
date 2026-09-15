# M6 Calibration Laboratory

M6 connects persistent measured swatches to the research calibration engine.

## Eligibility
A swatch is excluded when its measured yarn length is absent, referenced yarn/pattern is unavailable,
or its stitch/row grid cannot be represented as whole canonical pattern repeats for operation accounting.

## Readiness gate
Current project protocol requires at least 6 eligible swatches, 2 distinct patterns and 2 distinct yarns.
These are engineering protocol thresholds, not published universal calibration standards.

## Model
The existing ridge-regularized linear research model is fitted only after the readiness gate.
Training RMSE/MAE are reported. Leave-one-out validation is attempted where possible and explicitly
fails when a validation fold contains an operation unseen in training.

A fitted model is NOT automatically promoted to the production calculator.

## Evidence boundary
Measured data, eligibility, training fit, cross-validation and production promotion are distinct states.
