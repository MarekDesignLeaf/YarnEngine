import hashlib,json,datetime

def _sha(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

def dataset_snapshot(records):
    rows=[]
    for r in sorted(records,key=lambda x:x.record_id):
        rows.append({"record_id":r.record_id,"replicate_group_id":r.replicate_group_id,
          "crocheter_id":r.crocheter_id,"yarn_id":r.yarn_id,"hook_mm":r.hook_mm,
          "gauge_stitches":r.gauge_stitches,"gauge_rows":r.gauge_rows,
          "gauge_width_mm":r.gauge_width_mm,"gauge_height_mm":r.gauge_height_mm,
          "operation_counts":dict(sorted(r.operation_counts.items())),
          "yarn_length_m":r.yarn_length_m,"yarn_mass_g":r.yarn_mass_g,"tex":r.tex,
          "yarn_diameter_mm":r.yarn_diameter_mm,"construction":r.construction,
          "tension_condition":r.tension_condition,"evidence_reference":r.evidence_reference})
    return {"record_count":len(rows),"record_ids":[x["record_id"] for x in rows],
            "dataset_sha256":_sha(rows),"records":rows}

def calibration_audit(records, readiness, quality, consistency, fit=None, model=None):
    snap=dataset_snapshot(records)
    payload={"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "dataset":{"record_count":snap["record_count"],"record_ids":snap["record_ids"],
                 "dataset_sha256":snap["dataset_sha256"]},
      "readiness":readiness,"replicate_quality":quality,"measurement_consistency":consistency,
      "fit":fit,"registered_model":model}
    payload["audit_sha256"]=_sha(payload)
    return payload
