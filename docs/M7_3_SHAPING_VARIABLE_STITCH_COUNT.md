# M7.3 Shaping & Variable Stitch Count Grammar

M7.3 introduces a separate shaped-pattern model so ordinary repeat patterns remain backward compatible.

A shaped pattern declares `initial_stitches`. Each row is evaluated using canonical operation consume/produce counts.
The validator tracks a stitch-state transition:

`available before row -> consumed by row -> produced after row`

For every following row, its consumed stitch count must equal the number of live stitches produced by the previous row.

This supports deterministic increases and decreases already represented by canonical operations such as KFB, M1L/M1R,
YO and decreases such as K2TOG/SSK, subject to their registry semantics.

The result includes a row-by-row trace with `expected_in`, `consumed`, `produced`, and `delta`.

This milestone does not yet model spatial shaping positions, short rows, held stitches, multiple active needle groups,
seaming, stuffing geometry, or 3D surface reconstruction. It establishes the stitch-count state machine required for them.
