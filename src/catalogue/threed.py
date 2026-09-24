"""Canonical 3D and true 360 governance."""
from __future__ import annotations

ALLOWED_3D_FORMATS={"GLB","GLTF"}
ALLOWED_360_SOURCES={"CANONICAL_3D","PHYSICAL_TURNTABLE"}


def validate_canonical_3d(metadata:dict):
    m=dict(metadata or {})
    fmt=str(m.get("format") or "").upper()
    if fmt not in ALLOWED_3D_FORMATS:raise ValueError("Canonical 3D format must be GLB or GLTF")
    for key in ("physical_scale_unit","pivot","geometry_hash","materials_hash"):
        if not m.get(key):raise ValueError("Canonical 3D requires "+key)
    m["format"]=fmt
    m.setdefault("coordinate_convention",{
      "up":"+Y","front":"+Z","product_right":"-X","product_left":"+X",
      "azimuth_direction":"+Z toward -X"})
    return m


def validate_360_manifest(manifest:dict):
    m=dict(manifest or {})
    source=str(m.get("source") or "").upper()
    if source not in ALLOWED_360_SOURCES:
        raise ValueError("true 360 requires Canonical 3D or physical turntable")
    count=int(m.get("frame_count") or 0)
    if count<8:raise ValueError("360 frame_count must be at least 8")
    step=float(m.get("step_deg") or 0)
    if abs(step*count-360.0)>0.001:raise ValueError("360 step_deg × frame_count must equal 360")
    hashes=m.get("frame_hashes") or []
    if len(hashes)!=count or any(not h for h in hashes):raise ValueError("360 requires one hash per frame")
    if source=="CANONICAL_3D" and not m.get("canonical_3d_asset_id"):
        raise ValueError("Canonical 3D source requires canonical_3d_asset_id")
    m["source"]=source;m["frame_count"]=count;m["step_deg"]=step
    m.setdefault("start_azimuth_deg",0);m.setdefault("direction","+Z toward -X")
    return m
