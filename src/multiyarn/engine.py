from collections import Counter,defaultdict
def calculate_multiyarn(program, yarns, model_predictor):
    """Route canonical operation counts to explicit yarn carriers and aggregate per-yarn consumption.
    model_predictor(yarn_id, operation_counts) must return a governed prediction dict."""
    if not isinstance(program,list) or not program: raise ValueError("program required")
    known=set(yarns); counts=defaultdict(Counter); floats=defaultdict(float)
    for i,step in enumerate(program):
        y=step.get("yarn_id");op=step.get("op");n=int(step.get("n",0))
        if y not in known: raise ValueError(f"unknown yarn_id at step {i}: {y}")
        if not op or n<=0: raise ValueError(f"invalid operation at step {i}")
        counts[y][op]+=n
        fl=float(step.get("float_length_m",0) or 0)
        if fl<0:raise ValueError("float length cannot be negative")
        floats[y]+=fl
    per={};total=0.0
    for y,ops in counts.items():
        pred=model_predictor(y,dict(ops))
        core=float(pred["recommended_length_m"])+floats[y]
        per[y]={"operation_counts":dict(ops),"predicted_length_m":float(pred["recommended_length_m"]),
                "explicit_float_length_m":floats[y],"total_length_m":core,"prediction":pred}
        total+=core
    return {"per_yarn":per,"total_length_m":total,
      "audit":{"count_basis":"explicit carrier-routed canonical operation program",
               "float_policy":"only explicitly supplied float lengths are added; no invented colourwork float coefficient"}}
