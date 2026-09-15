
from .engine import load_events,apply_events

def analyse_stitch_groups(payload):
    try:
        events=load_events(payload.get("events",[]))
        return apply_events(int(payload.get("initial_stitches",0) or 0),events)
    except Exception as e:
        return {"valid":False,"issues":[{"code":"GROUP_MODEL_ERROR","message":str(e)}],"timeline":[]}
