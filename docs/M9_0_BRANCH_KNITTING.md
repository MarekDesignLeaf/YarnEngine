# M9.0 Independent Branch Knitting

Adds executable branch knitting on top of the M7.5 stitch-group topology and the populated M8.3 library.

A branch program can split a live group, hold or activate branches, work rows independently on each active branch, apply variable stitch-count operations inside a branch, and join branches later.

Canonical stitch operations are counted globally across all branch rows. Structural commands such as split, hold, activate and join are topology actions and are not counted as yarn-consuming stitch operations.

This is still a discrete knitting topology model. It does not model yarn carriers, colourwork strand routing, seam yarn, stuffing, elasticity or physical 3D surface geometry.
