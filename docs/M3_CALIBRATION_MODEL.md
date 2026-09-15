# M3 Calibration & Consumption Model

## Objective
Turn measured swatches into a fitted prediction model without inventing hand-entered consumption coefficients.

## Pipeline
1. Pattern/project geometry produces exact operation counts.
2. Calibration sample stores those counts plus measured yarn length and gauge geometry.
3. Feature engineering builds a reproducible numeric vector.
4. Ridge-regularized least squares fits coefficients from measured data.
5. Model stores fit metrics and the domain covered by calibration data.
6. Prediction checks whether the requested project is inside the calibrated domain.
7. Results include estimate, research-stage uncertainty range, warnings, model sample count and RMSE.

## Current features
* operation counts
* wale spacing
* course spacing
* yarn diameter when supplied
* intercept

## Current uncertainty
M3 uses residual standard deviation to construct an approximate 95% residual band.
This is intentionally labelled research-stage. It is NOT yet a rigorous regression prediction interval.
Out-of-domain predictions automatically receive a wider minimum uncertainty band and warnings.

## Calibration evidence rule
Production calibration records must be measured.
The included `synthetic_m3_test_dataset.json` exists only to test the software pipeline.
It must never be used as knitting evidence or shipped as a production model.

## Why ridge regression
Hundreds of patterns reuse a much smaller vocabulary of operations.
A regularized operation-level model can share evidence across patterns instead of requiring an independent coefficient for every named pattern.
As the dataset grows we can replace or extend this with hierarchical/Bayesian models without changing the upstream Pattern Engine.

## Next step
M3.1:
* real swatch capture workflow
* measurement provenance
* replicate handling
* train/validation split by knitter/yarn/pattern
* stronger uncertainty intervals
* family-level fallback for unseen operations
