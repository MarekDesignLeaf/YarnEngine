# M6.2 Production Model Integration

M6.2 introduces calibrated Tier C in the main calculator.

Tier priority is user-controlled:
- Tier A: measured swatch
- Tier C: explicitly approved production calibration model
- Tier B: research geometry baseline

Tier C never silently substitutes itself for a measured swatch. The user selects Approved model mode.
The runtime records the exact model ID, stage, creation time and promotion time in the calculation audit.

Before prediction the model checks operation coverage, wale/course spacing and yarn diameter against
its calibration domain. Out-of-domain use remains visible, widens the research-stage uncertainty band,
and changes model status to `production_model_out_of_domain`.

No production model means calibrated mode fails explicitly rather than falling back silently.

M6.2 also changes the application allowance default from 8% to 0%. Reserve yarn is now opt-in.
