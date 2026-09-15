# M2.1 Project Geometry

Implemented:
* explicit left/right edge zones
* full-repeat placement
* controlled partial repeat modes: reject, left, right, split, center
* vertical remainder rows
* physical size + gauge -> project grid
* project-wide operation counts
* conservative safety rejection when a partial repeat cuts through a multi-stitch operation
* explicit rejection of partial slicing through zero-consumption constructs such as yarn-over unless an edge fragment is authored
* ProjectGeometry schema

Invariant:
left edge + left partial + N × full repeat + right partial + right edge = total stitches.

No remainder stitch is hidden or guessed.
