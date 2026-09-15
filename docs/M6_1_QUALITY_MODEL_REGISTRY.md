# M6.1 Calibration Quality & Model Registry

M6.1 separates model creation from model approval.

Stages:
research -> candidate -> production -> retired

A research fit can never become production during fitting. Promotion is a separate explicit API/UI action.
Only one production model is allowed; promoting a candidate to production retires any previous production model.

Registered models preserve a data snapshot containing the swatch IDs and coverage used for training.

Replicate analysis reports sample SD and coefficient of variation. Current 3-replicate / 5% CV flags are
project quality-control thresholds, not universal standards. Diagnostic flags never delete observations automatically.
