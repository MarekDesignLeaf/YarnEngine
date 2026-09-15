# M2 Pattern Engine

## Goal
Represent hundreds or thousands of knitting patterns as versioned data rather than code.

## Implemented
* typed pattern domain
* JSON loader
* operation registry
* structural validation
* row numbering checks
* consumed/produced stitch accounting
* full horizontal and vertical repeat expansion
* aggregate operation counting
* structural pattern signatures
* human-readable Pattern DSL
* CLI inspection/validation
* canonical test patterns including rib, seed, cable and balanced eyelet

## Deliberate boundary
M2 currently expands only complete repeats.
Partial horizontal repeats, selvedges, pattern-specific borders and shaped rows are rejected.
This avoids silent assumptions. They become explicit features in M2.1/M3.

## Why this scales
The calculation engine no longer needs to know individual named patterns.
It only needs:
1. a validated operation vocabulary
2. a pattern definition
3. project stitch/row dimensions

A pattern can therefore be added without changing application code.

## Next
M2.1 should add explicit edge zones and partial-repeat policies.
M3 should attach consumption models to operation families and fit calibration corrections.
