
from src.shaping.service import translate_shaping
from src.shaping.loader import load_shaped_pattern_dict
from .topology import build_spatial_topology,topology_profile,approximate_2d_outline

def analyse_spatial_shaping(payload,operations):
    translated=translate_shaping(payload,operations)
    if not translated.get("valid"):
        return {**translated,"topology":None,"profile":None,"outline":None}
    pat=load_shaped_pattern_dict(translated["pattern"])
    topology=build_spatial_topology(pat,operations)
    profile=topology_profile(topology)
    outline=None
    gauge=payload.get("gauge_preview") or {}
    sw=gauge.get("stitch_width_mm")
    rh=gauge.get("row_height_mm")
    if sw is not None and rh is not None:
        outline=approximate_2d_outline(topology,float(sw),float(rh))
    return {**translated,"topology":topology,"profile":profile,"outline":outline}
