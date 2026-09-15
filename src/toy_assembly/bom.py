from collections import defaultdict
def aggregate_toy_bom(parts, assembly=None):
    if not parts:raise ValueError("at least one part required")
    assembly=assembly or []
    yarn=defaultdict(float);part_rows=[]
    for p in parts:
        name=p.get("part_id") or p.get("name")
        if not name:raise ValueError("part id required")
        cons=p.get("yarn_consumption_m") or {}
        if not cons:raise ValueError(f"part {name} has no yarn consumption")
        for y,m in cons.items():
            if float(m)<0:raise ValueError("negative consumption")
            yarn[y]+=float(m)
        part_rows.append({"part_id":name,"yarn_consumption_m":dict(cons)})
    assembly_rows=[]
    for x in assembly:
        y=x["yarn_id"];m=float(x["length_m"])
        if m<0:raise ValueError("negative assembly yarn")
        yarn[y]+=m;assembly_rows.append(dict(x))
    return {"parts":part_rows,"assembly":assembly_rows,"total_yarn_m":dict(yarn),
      "audit":{"assembly_policy":"sewing/embroidery/decorative yarn included only when explicitly measured or supplied"}}
