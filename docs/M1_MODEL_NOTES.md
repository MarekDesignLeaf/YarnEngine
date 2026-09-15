# M1 Calculation Model

## Tier A: empirical core-swatch scaling
The system stores measured yarn length for a known number of stitch positions in the same pattern.
metres_per_stitch_position = swatch_yarn_length / (swatch_stitches × swatch_rows)
project_core_length = metres_per_stitch_position × project_stitches × project_rows

The project stitch/row counts are generated from the measured gauge. This mode avoids inventing
a generic pattern coefficient.

## Tier B: theoretical plain-loop geometry
A = gauge_width_mm / gauge_stitches
B = gauge_height_mm / gauge_rows
d = yarn diameter in mm

Published element equations implemented:
single-bar needle loop:
l_s = 0.5 π (0.5 A + d) + 2 B

shortest horizontal float (i=2):
l_h = 0.5 π (0.5 A + d)

M1 plain-loop baseline:
l_plain = l_s + l_h

The final composition is an engineering interpretation of the published decomposition and is
explicitly marked unvalidated for hand knitting.

## Exclusions
No hidden waste factor.
Cast-on, bind-off, tails, seams, borders and shaping are not part of the rectangular core.
Allowance is user-visible and separately reported.
