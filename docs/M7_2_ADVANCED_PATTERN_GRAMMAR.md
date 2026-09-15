# M7.2 Advanced Pattern Grammar

M7.2 extends acquisition parsing while preserving deterministic topology.

Supported:
* explicit operation counts such as `K4`, `P 2`, `4 K`
* parenthesized groups with explicit repeat count, e.g. `(K2, P2) x4`
* bracketed groups with explicit repeat count, e.g. `[K2, P2] 4 times`
* `repeat to end` only when the preceding unit consumes a positive number of stitches and exactly tiles the declared repeat width

Rejected for manual review:
* non-tiling `repeat to end`
* zero-consumption repeat units
* nested groups
* groups without an explicit repeat multiplier
* `until`, `to last`, and other shaping/control prose
* side markers embedded in instruction prose

The parser expands accepted grammar into the same canonical flat operation sequence consumed by the existing Pattern Engine. It does not change canonical operation semantics.

This milestone still does not interpret shaping, conditional branches, multiple sizes, colourwork strands, or free-form natural-language pattern prose.
