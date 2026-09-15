# M9.4 Crochet Production Workflow

This milestone closes the software-side loop from physical crochet measurement to a governed model candidate.

Implemented:
1. Persistent SQLite storage for crochet calibration records.
2. CRUD API for real measurements.
3. Persistent readiness/coverage endpoint.
4. Fit-and-register endpoint.
5. Crochet models are registered with model_schema_version=m9-crochet-model-1 and scope=crochet.
6. Existing model registry governance remains authoritative for candidate and production promotion.
7. Existing strict OOD policy remains authoritative during complex-consumption calculation.

The system deliberately does not auto-promote a fitted crochet model to production. Real evidence must first satisfy the calibration readiness gate, model validation must exist, and the model registry production gate must pass.

Remaining non-software requirement:
Real physical measurements. Without measured crochet samples the application can be functionally complete but cannot truthfully claim calibrated production accuracy for crochet/amigurumi.
