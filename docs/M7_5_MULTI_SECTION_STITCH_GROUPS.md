# M7.5 Multi Section Parts & Stitch Groups

M7.5 introduces a topology state machine for multiple stitch groups.

Supported actions:
* split one active group into two or more named groups
* hold an active group
* resume a held group
* join two or more non-closed groups into a new group
* close a group

Every operation is validated against the current state. Split counts must exactly preserve the source stitch count.
Join operations preserve the combined stitch count. A timeline records each state transition.

This is a topology layer only. It does not yet assign row instructions independently to each group, model yarn carriers,
short rows, pick-up operations, grafting, sewing, or physical 3D positions of separate groups.
