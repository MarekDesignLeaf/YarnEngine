# M3.1 Real Calibration System

## Added
* real swatch evidence model
* replicate grouping
* repeatability summaries: mean, sample SD and CV
* configurable instability flags
* leave-one-group-out validation by knitter, yarn or pattern
* coverage reports for operations/patterns/yarns/knitters
* deterministic candidate-priority scoring
* blank real-measurement JSON template
* validation and measurement documentation

## Scientific rationale
NIST measurement-process guidance treats repeatability, reproducibility, stability and uncertainty as separate characteristics that should be evaluated rather than hidden inside one number.

For predictive validation, related measurements must not leak across training and validation folds. Grouped cross-validation provides a clean way to hold out complete knitters, yarns or patterns.

## Candidate priority
The candidate ranker is intentionally transparent rather than pretending to be mathematically optimal.
It gives higher scores to:
* unseen or under-covered stitch operations
* unseen pattern families
* unseen yarns
* unseen knitters
* gauge/yarn-diameter regions that extend the calibrated domain

Later, once enough real data exist, this can be replaced by formal optimal experimental design or Bayesian information-gain selection.

## Production rule
Synthetic M3 records remain test fixtures only.
M3.1 production models must be trained from records carrying measured evidence.
