# M8.1 Validation & Uncertainty

M8.1 replaces the implication that training residual spread is a production uncertainty interval.

## Held-out empirical interval
When held-out validation errors are available, runtime predictions use the requested quantile of absolute held-out errors as a symmetric empirical coverage interval around the estimate.

This is deliberately named an empirical held-out error interval, not a formal parametric regression prediction interval.

With fewer than 20 held-out errors the result is explicitly marked descriptive and not production validated. The threshold is a software evidence flag, not a universal statistical standard.

## Fallback
When no held-out errors are stored, the previous 1.96 x training residual standard deviation calculation remains only as an explicitly warned research fallback.

## Out-of-domain
M8 strict/warn/research policy remains authoritative. Strict mode rejects out-of-domain production predictions before returning a result. Warn/research modes widen uncertainty to at least 25 percent of the estimate and report the domain violation.

## Promotion gate
Production promotion is additionally blocked when validation contains failed folds. No arbitrary RMSE or percentage accuracy threshold is invented. Such acceptance limits require a real calibration programme and product requirement.

## API
POST /api/validation/uncertainty
returns the empirical interval and validation summary.

No real production accuracy claim is made by this milestone.
