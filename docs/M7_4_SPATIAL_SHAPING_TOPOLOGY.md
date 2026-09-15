# M7.4 Spatial Shaping & 3D Part Topology

M7.4 adds positional topology on top of M7.3 stitch-count continuity.

Every individual canonical operation receives:
* input stitch span
* output stitch span
* consumed and produced counts
* local stitch-count delta
* normalized input and output centre positions

This lets the engine distinguish two patterns with the same total stitch counts but different placement of increases/decreases.

The topology profile exposes row-level increase and decrease positions normalized across row width.

An optional 2D outline preview uses caller-supplied stitch width and row height. It is explicitly a stitch-count geometric preview.
It is not a physical simulation of knitted fabric, drape, elasticity, stuffing, curvature, or a validated 3D reconstruction.

This establishes the topology needed for later spatial sections, short rows, held stitches, part joining and 3D surface models.
