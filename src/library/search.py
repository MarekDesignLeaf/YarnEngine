def search_yarns(registry,*,text=None,cyc_weight=None,fibre=None,min_length_m=None):
    q=(text or "").lower().strip()
    out=[]
    for y in registry.yarns.values():
        if cyc_weight is not None and y.cyc_weight!=cyc_weight: continue
        if fibre and fibre.lower() not in {k.lower() for k in y.fibre_composition}: continue
        if min_length_m is not None and y.package_length_m<min_length_m: continue
        hay=" ".join(filter(None,[y.brand,y.product,y.variant or "",y.yarn_id])).lower()
        if q and q not in hay: continue
        out.append(y)
    return tuple(sorted(out,key=lambda x:(x.brand.lower(),x.product.lower(),x.yarn_id)))

def search_patterns(registry,*,text=None,family_id=None,tags=(),techniques=(),difficulty=None,active_only=True):
    q=(text or "").lower().strip()
    req_tags={x.lower() for x in tags}; req_tech={x.lower() for x in techniques}
    out=[]
    for key,m in registry.pattern_metadata.items():
        if active_only and not m.active: continue
        if family_id and m.family_id!=family_id: continue
        if difficulty and m.difficulty!=difficulty: continue
        if not req_tags.issubset({x.lower() for x in m.tags}): continue
        if not req_tech.issubset({x.lower() for x in m.techniques}): continue
        hay=" ".join([m.pattern_id,m.name,m.family_id,*m.tags,*m.techniques]).lower()
        if q and q not in hay: continue
        out.append(m)
    return tuple(sorted(out,key=lambda x:(x.name.lower(),x.version)))
