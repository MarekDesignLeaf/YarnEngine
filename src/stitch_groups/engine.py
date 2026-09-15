
from dataclasses import asdict
from .model import StitchGroup,GroupEvent

def _snapshot(groups):
    return {gid:asdict(g) for gid,g in sorted(groups.items())}

def apply_events(initial_stitches:int,events:list[GroupEvent]):
    if initial_stitches<=0:
        return {"valid":False,"issues":[{"code":"INITIAL_STITCHES_REQUIRED","message":"initial_stitches must be > 0"}],"timeline":[]}
    groups={"G0":StitchGroup("G0",initial_stitches,"active",())}
    issues=[];timeline=[{"step":0,"event":"initial","groups":_snapshot(groups)}]

    for e in sorted(events,key=lambda x:x.step):
        if e.action=="hold":
            if len(e.source_ids)!=1:
                issues.append({"code":"HOLD_SOURCE_REQUIRED","step":e.step});continue
            gid=e.source_ids[0];g=groups.get(gid)
            if not g or g.state!="active":
                issues.append({"code":"HOLD_INVALID_SOURCE","step":e.step,"group_id":gid});continue
            groups[gid]=StitchGroup(g.group_id,g.stitches,"held",g.parent_ids)

        elif e.action=="resume":
            if len(e.source_ids)!=1:
                issues.append({"code":"RESUME_SOURCE_REQUIRED","step":e.step});continue
            gid=e.source_ids[0];g=groups.get(gid)
            if not g or g.state!="held":
                issues.append({"code":"RESUME_INVALID_SOURCE","step":e.step,"group_id":gid});continue
            groups[gid]=StitchGroup(g.group_id,g.stitches,"active",g.parent_ids)

        elif e.action=="close":
            if len(e.source_ids)!=1:
                issues.append({"code":"CLOSE_SOURCE_REQUIRED","step":e.step});continue
            gid=e.source_ids[0];g=groups.get(gid)
            if not g or g.state=="closed":
                issues.append({"code":"CLOSE_INVALID_SOURCE","step":e.step,"group_id":gid});continue
            groups[gid]=StitchGroup(g.group_id,0,"closed",g.parent_ids)

        elif e.action=="split":
            if len(e.source_ids)!=1 or len(e.target_ids)<2 or len(e.counts)!=len(e.target_ids):
                issues.append({"code":"SPLIT_SHAPE_INVALID","step":e.step});continue
            gid=e.source_ids[0];g=groups.get(gid)
            if not g or g.state!="active":
                issues.append({"code":"SPLIT_INVALID_SOURCE","step":e.step,"group_id":gid});continue
            if any(c<=0 for c in e.counts):
                issues.append({"code":"SPLIT_COUNT_INVALID","step":e.step});continue
            if sum(e.counts)!=g.stitches:
                issues.append({"code":"SPLIT_COUNT_MISMATCH","step":e.step,"available":g.stitches,"requested":sum(e.counts)});continue
            if len(set(e.target_ids))!=len(e.target_ids) or any(t in groups for t in e.target_ids):
                issues.append({"code":"SPLIT_TARGET_CONFLICT","step":e.step});continue
            groups[gid]=StitchGroup(g.group_id,0,"closed",g.parent_ids)
            for tid,c in zip(e.target_ids,e.counts):
                groups[tid]=StitchGroup(tid,c,"active",(gid,))

        elif e.action=="join":
            if len(e.source_ids)<2 or len(e.target_ids)!=1:
                issues.append({"code":"JOIN_SHAPE_INVALID","step":e.step});continue
            src=[]
            for gid in e.source_ids:
                g=groups.get(gid)
                if not g or g.state=="closed":
                    issues.append({"code":"JOIN_INVALID_SOURCE","step":e.step,"group_id":gid})
                    src=[];break
                src.append(g)
            if not src:continue
            tid=e.target_ids[0]
            if tid in groups:
                issues.append({"code":"JOIN_TARGET_CONFLICT","step":e.step,"group_id":tid});continue
            total=sum(g.stitches for g in src)
            for g in src:
                groups[g.group_id]=StitchGroup(g.group_id,0,"closed",g.parent_ids)
            groups[tid]=StitchGroup(tid,total,"active",tuple(e.source_ids))

        timeline.append({"step":e.step,"event":e.action,"groups":_snapshot(groups)})

    live=sum(g.stitches for g in groups.values() if g.state!="closed")
    return {"valid":not issues,"issues":issues,"timeline":timeline,
            "groups":_snapshot(groups),"live_stitches":live}

def load_events(raw):
    return [GroupEvent(
        step=int(x["step"]),action=str(x["action"]),
        source_ids=tuple(x.get("source_ids",[])),
        target_ids=tuple(x.get("target_ids",[])),
        counts=tuple(int(c) for c in x.get("counts",[])),
        note=x.get("note")
    ) for x in raw]
