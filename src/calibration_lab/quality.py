from collections import defaultdict
from math import sqrt

def replicate_quality(swatches,cv_threshold_percent=5.0,min_replicates=3):
 groups=defaultdict(list)
 for s in swatches:
  gid=s.get("replicate_group_id")
  if gid and s.get("yarn_length_m") is not None:groups[gid].append(float(s["yarn_length_m"]))
 out=[];flags=[]
 for gid,vals in sorted(groups.items()):
  n=len(vals);mean=sum(vals)/n;sd=sqrt(sum((x-mean)**2 for x in vals)/(n-1)) if n>1 else 0
  cv=sd/mean*100 if mean else None
  row={"replicate_group_id":gid,"n":n,"mean_length_m":mean,"sample_sd_m":sd,"cv_percent":cv}
  out.append(row)
  if n<min_replicates:flags.append({"group":gid,"code":"insufficient_replicates","value":n})
  elif cv is not None and cv>cv_threshold_percent:flags.append({"group":gid,"code":"high_cv_percent","value":cv})
 return {"groups":out,"flags":flags,"protocol":{"min_replicates":min_replicates,"cv_threshold_percent":cv_threshold_percent,
 "note":"Project quality-control thresholds, not universal standards."}}

def residual_outliers(actual,predicted,z_threshold=2.5):
 if len(actual)!=len(predicted):raise ValueError("length mismatch")
 residuals=[a-p for a,p in zip(actual,predicted)]
 if len(residuals)<3:return {"residuals":residuals,"flagged":[],"z_threshold":z_threshold}
 mean=sum(residuals)/len(residuals);sd=sqrt(sum((x-mean)**2 for x in residuals)/(len(residuals)-1))
 flagged=[]
 if sd:
  for i,r in enumerate(residuals):
   z=(r-mean)/sd
   if abs(z)>z_threshold:flagged.append({"index":i,"residual":r,"z":z})
 return {"residuals":residuals,"flagged":flagged,"z_threshold":z_threshold,
 "warning":"Residual flags are diagnostics only; records are never automatically deleted."}
