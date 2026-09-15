from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import CalculationRequest, EditorPatternInput, SavePatternRequest, ProjectCreateRequest, ProjectUpdateRequest, YarnCreateRequest, SwatchCreateRequest
from .bootstrap import ensure_demo_database
from .service import WebService
from .pattern_chart import build_pattern_chart, load_operation_map
from src.pattern_engine.loader import load_pattern_file
from src.pattern_editor.model import EditorPattern, EditorCell
from src.pattern_editor.validation import validate_editor_grid
from src.pattern_editor.convert import editor_to_canonical_dict
from src.pattern_engine.loader import load_pattern_dict
from src.pattern_engine.validation import validate_pattern
import json, re
from src.projects.store import ProjectStore
from src.swatch_manager.store import SwatchStore
from src.calibration_lab.analysis import build_lab_record,readiness
from src.calibration_lab.fit import fit_report
from src.calibration_lab.quality import replicate_quality
from src.model_registry.store import ModelRegistry
from src.pattern_import_studio.studio import inspect_bundle,batch_inspect
from src.pattern_import_studio.accept import accept_bundle
from src.pattern_acquisition.pipeline import acquire_structured_text
from src.shaping.service import translate_shaping
from src.spatial_shaping.service import analyse_spatial_shaping
from src.stitch_groups.service import analyse_stitch_groups
from src.library.yarn import YarnRecord
from src.import_pipeline.core import canonical_checksum
from src.calibration.uncertainty import empirical_absolute_error_interval, validation_summary
from src.library_scaling.batch import inspect_scaling_batch
from src.library_scaling.pipeline import scale_gate
from src.branch_knitting.engine import execute_branch_program
from src.crochet.amigurumi import analyse_rounds
from src.complex_consumption.bridge import calculate_operation_program
from src.gauge_engine.gauge import Gauge
from src.crochet_calibration.record import CrochetCalibrationRecord
from src.crochet_calibration.protocol import readiness as crochet_calibration_readiness
from src.crochet_calibration.fit import fit_crochet_model
from src.crochet_calibration.store import CrochetCalibrationStore
from src.crochet_calibration.experiment import generate_experiment_plan
from src.crochet_calibration.quality import replicate_quality as crochet_replicate_quality, measurement_consistency
from src.crochet_calibration.audit import dataset_snapshot, calibration_audit
from src.multiyarn.engine import calculate_multiyarn
from src.toy_assembly.bom import aggregate_toy_bom
import datetime

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data/db/web_app.sqlite"
STATIC = Path(__file__).resolve().parent / "static"

ensure_demo_database(ROOT, DB_PATH)
model_registry = ModelRegistry(ROOT / 'data/db/model_registry.sqlite')
service = WebService(ROOT, DB_PATH, model_registry=model_registry)
project_store = ProjectStore(ROOT / 'data/db/projects.sqlite')
swatch_store = SwatchStore(ROOT / 'data/db/swatches.sqlite')
crochet_cal_store = CrochetCalibrationStore(ROOT / 'data/db/crochet_calibration.sqlite')
operation_map = load_operation_map(ROOT)

app = FastAPI(
    title="Yarn Consumption Engine",
    version="M11.0",
    description="Pattern-aware yarn consumption calculator with measured-swatch and research geometry modes.",
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

@app.get("/sw.js")
def service_worker():
    return FileResponse(STATIC / "sw.js", media_type="application/javascript", headers={"Service-Worker-Allowed": "/"})

@app.get("/manifest.webmanifest")
def web_manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "M11.0"}


def _existing_pattern_rows():
 store=service._store()
 try:return [dict(r) for r in store.conn.execute("SELECT pattern_id,version,checksum FROM patterns")]
 finally:store.close()

@app.post("/api/toy/bom")
def toy_bom(payload:dict):
    try:return aggregate_toy_bom(payload.get("parts",[]),payload.get("assembly",[]))
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(status_code=422,detail=str(e))

@app.post("/api/multiyarn/aggregate")
def multiyarn_aggregate(payload:dict):
    """Aggregate already governed per-yarn predictions. This endpoint never invents a model."""
    predictions=payload.get("predictions",{})
    def predictor(yarn_id,ops):
        p=predictions.get(yarn_id)
        if not p:raise ValueError(f"missing governed prediction for yarn {yarn_id}")
        expected=p.get("operation_counts")
        if expected is not None and expected!=ops:raise ValueError(f"prediction operation counts do not match carrier program for {yarn_id}")
        if "recommended_length_m" not in p:raise ValueError("recommended_length_m missing")
        return p
    try:return calculate_multiyarn(payload.get("program",[]),payload.get("yarns",{}),predictor)
    except (ValueError,KeyError,TypeError) as e:raise HTTPException(status_code=422,detail=str(e))

@app.get("/api/crochet/calibration/audit")
def crochet_calibration_audit():
    records=crochet_cal_store.records()
    gate=crochet_calibration_readiness(records)
    qc=crochet_replicate_quality(records)
    consistency=measurement_consistency(records)
    return calibration_audit(records,gate,qc,consistency)

@app.get("/api/crochet/calibration/dataset-snapshot")
def crochet_calibration_dataset_snapshot():
    return dataset_snapshot(crochet_cal_store.records())

@app.get("/api/crochet/calibration/quality")
def crochet_calibration_quality(warn_cv:float=0.10, fail_cv:float=0.20, mass_length_tolerance:float=0.15):
    if not (0 <= warn_cv < fail_cv):raise HTTPException(status_code=422,detail="require 0 <= warn_cv < fail_cv")
    records=crochet_cal_store.records()
    return {"replicates":crochet_replicate_quality(records,warn_cv,fail_cv),
            "consistency":measurement_consistency(records,mass_length_tolerance)}

@app.post("/api/crochet/calibration/experiment-plan")
def crochet_calibration_experiment_plan(payload:dict):
    try:
        return generate_experiment_plan(
          crochet_cal_store.records(),
          required_ops=tuple(payload.get("required_ops",["SC","SC_INC","SC2TOG","SC_BLO","SC_FLO","SLST","CH"])),
          min_records_per_op=int(payload.get("min_records_per_op",3)),
          min_replicates=int(payload.get("min_replicates",3)),
          yarn_id=payload.get("yarn_id"),crocheter_id=payload.get("crocheter_id"),
          hook_mm=float(payload["hook_mm"]) if payload.get("hook_mm") not in (None,"") else None,
          construction=payload.get("construction","spiral"))
    except (TypeError,ValueError) as e:
        raise HTTPException(status_code=422,detail=str(e))

@app.get("/api/crochet/calibration/records")
def crochet_calibration_records():
    return crochet_cal_store.list()

@app.post("/api/crochet/calibration/records")
def crochet_calibration_add(payload:dict):
    try:
        rec=CrochetCalibrationRecord(**payload)
        return crochet_cal_store.add(rec)
    except (TypeError,ValueError) as e:
        raise HTTPException(status_code=422,detail=str(e))
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):raise HTTPException(status_code=409,detail="record_id already exists")
        raise

@app.delete("/api/crochet/calibration/records/{record_id}")
def crochet_calibration_delete(record_id:str):
    if not crochet_cal_store.delete(record_id):raise HTTPException(status_code=404,detail="record not found")
    return {"deleted":True,"record_id":record_id}

@app.get("/api/crochet/calibration/status")
def crochet_calibration_persistent_status():
    return crochet_calibration_readiness(crochet_cal_store.records())

@app.post("/api/crochet/calibration/fit-register")
def crochet_calibration_fit_register(payload:dict):
    records=crochet_cal_store.records()
    gate=crochet_calibration_readiness(records,
      required_ops=tuple(payload.get("required_ops",["SC","SC_INC","SC2TOG","SC_BLO","SC_FLO","SLST","CH"])),
      min_records_per_op=int(payload.get("min_records_per_op",3)),
      min_replicates=int(payload.get("min_replicates",3)))
    if not gate["ready"]:raise HTTPException(status_code=422,detail={"message":"crochet calibration evidence gate failed","gate":gate})
    qc=crochet_replicate_quality(records,float(payload.get("warn_cv",0.10)),float(payload.get("fail_cv",0.20)))
    consistency=measurement_consistency(records,float(payload.get("mass_length_tolerance",0.15)))
    if qc["overall"]=="fail" or not consistency["valid"]:
        raise HTTPException(status_code=422,detail={"message":"crochet calibration quality gate failed","replicates":qc,"consistency":consistency})
    try: report=fit_crochet_model(records,float(payload.get("ridge_lambda",1e-6)))
    except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
    validation=report.get("leave_one_out") or {}
    if report.get("validation_error"):validation={"validation_error":report["validation_error"]}
    ds=dataset_snapshot(records)
    snapshot={"scope":"crochet","coverage":gate["coverage"],
              "record_ids":[r.record_id for r in records],"dataset_sha256":ds["dataset_sha256"],
              "evidence_gate":gate,"replicate_quality":qc,"measurement_consistency":consistency}
    created=model_registry.create(payload.get("name","Crochet calibration candidate"),
      report["model"],validation,snapshot,
      model_schema_version="m9-crochet-model-1",feature_spec_version="m8-feature-spec-1")
    audit=calibration_audit(records,gate,qc,consistency,fit=report,model={"model_id":created["model_id"],"stage":created["stage"]})
    return {"model":created,"fit":report,"evidence_gate":gate,"replicate_quality":qc,"consistency":consistency,"audit":audit}

@app.post("/api/crochet/calibration/readiness")
def crochet_calibration_status(payload:dict):
    try:
        records=[CrochetCalibrationRecord(**x) for x in payload.get("records",[])]
        return crochet_calibration_readiness(records,
          required_ops=tuple(payload.get("required_ops",["SC","SC_INC","SC2TOG","SC_BLO","SC_FLO","SLST","CH"])),
          min_records_per_op=int(payload.get("min_records_per_op",3)),
          min_replicates=int(payload.get("min_replicates",3)))
    except (TypeError,ValueError) as e:
        raise HTTPException(status_code=422,detail=str(e))

@app.post("/api/complex-consumption/calculate")
def complex_consumption_calculate(payload:dict):
    kind=payload.get("program_type")
    program=payload.get("program",{})
    if kind=="amigurumi":
        analysed=analyse_rounds(program,service.operations)
    elif kind=="branch":
        analysed=execute_branch_program(program,service.operations)
    else:
        raise HTTPException(status_code=422,detail="program_type must be amigurumi or branch")
    if not analysed.get("valid"):
        raise HTTPException(status_code=422,detail={"program_issues":analysed.get("issues",[])})
    production=model_registry.production()
    if production is None:
        raise HTTPException(status_code=422,detail="no approved production calibration model")
    yarn=service._yarn(payload.get("yarn_id")) if payload.get("yarn_id") else None
    diameter=(yarn.get("nominal_diameter_mm") if yarn else None) or payload.get("yarn_diameter_mm")
    if diameter is None:
        raise HTTPException(status_code=422,detail="yarn diameter is required")
    gauge=Gauge(float(payload["gauge_stitches_per_10cm"]),float(payload["gauge_rows_per_10cm"]),100.0,100.0)
    try:
        calc,pred,audit=calculate_operation_program(
            record=production,operation_counts=analysed["operation_counts"],gauge=gauge,
            yarn_diameter_mm=float(diameter),allowance_percent=float(payload.get("allowance_percent",0)),
            tex=(yarn.get("tex") if yarn else None),package_length_m=(yarn.get("package_length_m") if yarn else None),
            domain_policy=payload.get("domain_policy","strict"),source=kind)
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e))
    return {"program_type":kind,"program_analysis":analysed,"calculation":calc.__dict__,
            "prediction":{"estimate_m":pred.estimate_m,"in_domain":pred.in_domain,"warnings":pred.warnings},
            "audit":audit,"model_id":production["model_id"]}

@app.post("/api/crochet/amigurumi/analyse")
def crochet_amigurumi_analyse(payload:dict):
    rounds=payload.get("rounds",[])
    if not isinstance(rounds,list) or len(rounds)>5000:
        raise HTTPException(status_code=422,detail="rounds must be a list with at most 5000 entries")
    return analyse_rounds(payload,service.operations)

@app.post("/api/branch-knitting/execute")
def branch_knitting_execute(payload:dict):
    steps=payload.get("steps",[])
    if not isinstance(steps,list) or len(steps)>5000:
        raise HTTPException(status_code=422,detail="steps must be a list with at most 5000 entries")
    return execute_branch_program(payload,service.operations)

@app.post("/api/library-scaling/inspect")
def library_scaling_inspect(payload:dict):
    items=payload.get("items",[])
    if not isinstance(items,list) or len(items)>5000:
        raise HTTPException(status_code=422,detail="items must be a list with at most 5000 entries")
    return inspect_scaling_batch(items,service.operations)

@app.post("/api/library-scaling/gate")
def library_scaling_gate(payload:dict):
    items=payload.get("items",[])
    target=int(payload.get("target",100))
    if target<1 or target>10000:raise HTTPException(status_code=422,detail="target out of range")
    if not isinstance(items,list) or len(items)>10000:raise HTTPException(status_code=422,detail="items limit exceeded")
    return scale_gate(items,target)

@app.post("/api/validation/uncertainty")
def validation_uncertainty(payload:dict):
    try:
        estimate=float(payload["estimate_m"])
        errors=payload.get("validation_errors",[])
        confidence=float(payload.get("confidence",0.95))
        interval=empirical_absolute_error_interval(estimate,errors,confidence)
        return {"interval":interval.__dict__,"validation":validation_summary(errors)}
    except (KeyError,TypeError,ValueError) as e:
        raise HTTPException(status_code=422,detail=str(e))

@app.post("/api/stitch-groups/analyse")
def stitch_groups_analyse(payload:dict):
    events=payload.get("events",[])
    if not isinstance(events,list) or len(events)>1000:
        raise HTTPException(status_code=422,detail="events must be a list with at most 1000 entries")
    return analyse_stitch_groups(payload)

@app.post("/api/spatial-shaping/analyse")
def spatial_shaping_analyse(payload:dict):
    rows=payload.get("rows",[])
    if not isinstance(rows,list) or len(rows)>1000:
        raise HTTPException(status_code=422,detail="rows must be a list with at most 1000 entries")
    return analyse_spatial_shaping(payload,service.operations)

@app.post("/api/shaping/translate")
def shaping_translate(payload:dict):
    rows=payload.get("rows",[])
    if not isinstance(rows,list) or len(rows)>1000:
        raise HTTPException(status_code=422,detail="rows must be a list with at most 1000 entries")
    return translate_shaping(payload,service.operations)

@app.post("/api/acquisition/translate")
def acquisition_translate(payload:dict):
    rows=payload.get("rows",[])
    if not isinstance(rows,list) or len(rows)>500:
        raise HTTPException(status_code=422,detail="rows must be a list with at most 500 entries")
    return acquire_structured_text(payload,service.operations,_existing_pattern_rows())

@app.post("/api/import-studio/inspect")
def import_studio_inspect(payload:dict):
 return inspect_bundle(payload,service.operations,_existing_pattern_rows())

@app.post("/api/import-studio/batch-inspect")
def import_studio_batch(payload:list[dict]):
 if len(payload)>1000:raise HTTPException(status_code=413,detail="batch limit is 1000 patterns")
 return batch_inspect(payload,service.operations,_existing_pattern_rows())

@app.post("/api/import-studio/accept")
def import_studio_accept(payload:dict):
 report=inspect_bundle(payload,service.operations,_existing_pattern_rows())
 if not report["valid"]:raise HTTPException(status_code=422,detail={"message":"pattern validation failed","issues":report["issues"]})
 if report["duplicate"]:raise HTTPException(status_code=409,detail=report["duplicate"])
 store=service._store()
 try:
  try:return accept_bundle(ROOT,store,report["bundle"],service.operations,allow_review=False)
  except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
 finally:store.close()

@app.get("/api/patterns")
def patterns():
    base={(x["pattern_id"],x["version"]):x for x in service.patterns()}
    meta_path=ROOT/"data/library/pattern_metadata.json"
    if meta_path.exists():
        for m in json.loads(meta_path.read_text()).get("patterns",[]):
            key=(m["pattern_id"],m["version"])
            if key not in base:
                base[key]={
                  "pattern_id":m["pattern_id"],"version":m["version"],"name":m["name"],
                  "family_id":m.get("family_id","CUSTOM"),"difficulty":m.get("difficulty","unknown"),
                  "tags":m.get("tags",[]),"techniques":m.get("techniques",[]),
                  "source_type":m.get("source_type","user_created")
                }
    return sorted(base.values(),key=lambda x:(x["name"],x["version"]))


@app.get("/api/patterns/{pattern_id}/{version}/chart")
def pattern_chart(pattern_id: str, version: str):
    path = None
    for candidate in (ROOT / "data/patterns").glob("*.json"):
        try:
            pattern = load_pattern_file(candidate)
        except Exception:
            continue
        if pattern.pattern_id == pattern_id and pattern.version == version:
            path = candidate
            break
    if path is None:
        raise HTTPException(status_code=404, detail="pattern version not found")
    pattern = load_pattern_file(path)
    return build_pattern_chart(pattern, operation_map)



def _editor_domain(x: EditorPatternInput):
    return EditorPattern(
        pattern_id=x.pattern_id,
        version=x.version,
        name=x.name,
        width=x.width,
        height=x.height,
        cells=tuple(EditorCell(c.row,c.col,c.operation_id,c.span) for c in x.cells),
    )


@app.get("/api/projects")
def list_projects():
    return project_store.list()

@app.get("/api/projects/{project_id}")
def get_project(project_id:int):
    p=project_store.get(project_id)
    if p is None:
        raise HTTPException(status_code=404,detail="project not found")
    return p

@app.post("/api/projects")
def create_project(request: ProjectCreateRequest):
    calc=request.calculation.model_dump()
    return project_store.create(
      name=request.name,
      description=request.description,
      pattern_id=calc["pattern_id"],
      pattern_version=calc["pattern_version"],
      yarn_id=calc.get("yarn_id"),
      request=calc,
      result=request.result,
      status=request.status
    )

@app.put("/api/projects/{project_id}")
def update_project(project_id:int, request:ProjectUpdateRequest):
    changes={}
    if request.name is not None: changes["name"]=request.name
    if request.description is not None: changes["description"]=request.description
    if request.status is not None: changes["status"]=request.status
    if request.calculation is not None:
        calc=request.calculation.model_dump()
        changes.update(pattern_id=calc["pattern_id"],pattern_version=calc["pattern_version"],
                       yarn_id=calc.get("yarn_id"),request=calc)
    if request.result is not None: changes["result"]=request.result
    p=project_store.update(project_id,**changes)
    if p is None:
        raise HTTPException(status_code=404,detail="project not found")
    return p

@app.post("/api/projects/{project_id}/calculate")
def calculate_project(project_id:int):
    p=project_store.get(project_id)
    if p is None:raise HTTPException(status_code=404,detail="project not found")
    try:
        req=CalculationRequest(**p["request"])
        result=service.calculate(req)
    except (ValueError,KeyError) as e:
        raise HTTPException(status_code=422,detail=str(e))
    return project_store.update(project_id,result=result,status="calculated")

@app.delete("/api/projects/{project_id}")
def delete_project(project_id:int):
    if not project_store.delete(project_id):
        raise HTTPException(status_code=404,detail="project not found")
    return {"status":"deleted","project_id":project_id}

@app.get("/api/operations")
def operations():
    return [
        {
          "operation_id":k,
          "name":v.get("name",k),
          "family":v.get("family","unknown"),
          "consumes_stitches":v.get("consumes_stitches",0),
          "produces_stitches":v.get("produces_stitches",0),
        }
        for k,v in sorted(operation_map.items())
    ]

@app.post("/api/editor/validate")
def editor_validate(request: EditorPatternInput):
    editor=_editor_domain(request)
    issues=validate_editor_grid(editor,operation_map)
    canonical=editor_to_canonical_dict(editor)
    canonical_issues=[]
    try:
        p=load_pattern_dict(canonical)
        report=validate_pattern(p,operation_map)
        canonical_issues=[{"code":i.code,"message":i.message} for i in report.issues]
    except Exception as e:
        canonical_issues=[{"code":"CANONICAL_ERROR","message":str(e)}]
    return {
      "valid": not issues and not canonical_issues,
      "grid_issues":[i.__dict__ for i in issues],
      "canonical_issues":canonical_issues,
      "canonical":canonical,
    }

@app.post("/api/editor/save")
def editor_save(request: SavePatternRequest):
    editor=_editor_domain(request.pattern)
    issues=validate_editor_grid(editor,operation_map)
    if issues:
        raise HTTPException(status_code=422,detail=[i.__dict__ for i in issues])
    canonical=editor_to_canonical_dict(editor)
    pattern=load_pattern_dict(canonical)
    report=validate_pattern(pattern,operation_map)
    if not report.valid:
        raise HTTPException(status_code=422,detail=[{"code":i.code,"message":i.message} for i in report.issues])

    safe=re.sub(r"[^A-Za-z0-9_.-]+","_",editor.pattern_id)
    dest=ROOT/"data/patterns"/f"user_{safe}_{editor.version}.json"
    if dest.exists():
        raise HTTPException(status_code=409,detail="pattern version already exists")
    dest.write_text(json.dumps(canonical,indent=2),encoding="utf-8")

    meta_path=ROOT/"data/library/pattern_metadata.json"
    meta=json.loads(meta_path.read_text())
    entry={
      "pattern_id":editor.pattern_id,"version":editor.version,"name":editor.name,
      "family_id":request.family_id,"tags":request.tags,"difficulty":request.difficulty,
      "techniques":request.techniques,"source_type":"user_created","source_reference":None,
      "license_id":None,"active":True
    }
    meta["patterns"].append(entry)
    meta_path.write_text(json.dumps(meta,indent=2),encoding="utf-8")
    return {"status":"saved","path":str(dest.relative_to(ROOT)),"pattern":canonical,"metadata":entry}


@app.post("/api/yarns")
def create_yarn(request:YarnCreateRequest):
    d=request.model_dump()
    YarnRecord(**d,source_type="user_created",evidence_level="user_declared")
    d["source_type"]="user_created";d["source_reference"]="web_yarn_manager";d["evidence_level"]="user_declared"
    checksum=canonical_checksum(d)
    store=service._store()
    try:
        if store.conn.execute("SELECT 1 FROM yarns WHERE yarn_id=?",(d["yarn_id"],)).fetchone():
            raise HTTPException(status_code=409,detail="yarn_id already exists")
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        store.upsert_yarn(d,checksum,now)
        store.audit(entity_type="yarn",entity_id=d["yarn_id"],version=None,source_type=d["source_type"],
                    source_reference=d["source_reference"],license_id=None,evidence_level=d["evidence_level"],
                    checksum=checksum,imported_at=now)
    finally: store.close()
    return {"status":"created","yarn":d}


def _eligible_lab_records():
    records=[];excluded=[]
    for s in swatch_store.list():
        try:
            if s.get("yarn_length_m") is None: raise ValueError("measured yarn length missing")
            yarn=service._yarn(s["yarn_id"])
            if yarn is None: raise ValueError("yarn missing")
            pattern,_,_=service._pattern(s["pattern_id"],s["pattern_version"])
            records.append(build_lab_record(s,yarn,pattern))
        except Exception as e:
            excluded.append({"swatch_id":s["swatch_id"],"reason":str(e)})
    return records,excluded


@app.get("/api/calibration-lab/quality")
def calibration_quality():
    return replicate_quality(swatch_store.list())

@app.get("/api/models/production/current")
def current_production_model():
    m=model_registry.production()
    if m is None:return {"active":False,"model":None}
    return {"active":True,"model":{"model_id":m["model_id"],"name":m["name"],"stage":m["stage"],
      "n_samples":m["model"]["n_samples"],"rmse_m":m["model"]["rmse_m"],"promoted_at":m["promoted_at"]}}

@app.get("/api/models")
def list_models():
    return model_registry.list()

@app.get("/api/models/{model_id}")
def get_model(model_id:str):
    m=model_registry.get(model_id)
    if m is None:raise HTTPException(status_code=404,detail="model not found")
    return m

@app.post("/api/calibration-lab/fit-and-register")
def fit_and_register(payload:dict={}):
    records,excluded=_eligible_lab_records();gate=readiness(records)
    if not gate["ready"]:
        raise HTTPException(status_code=422,detail={"message":"calibration readiness gate failed","reasons":gate["reasons"],"excluded":excluded})
    try:report=fit_report(records)
    except ValueError as e:raise HTTPException(status_code=422,detail={"message":"model fit failed","reason":str(e)})
    snapshot={"swatch_ids":[r.swatch_id for r in records],"coverage":gate["coverage"],"excluded":excluded}
    name=payload.get("name") or f"Calibration {len(model_registry.list())+1}"
    return model_registry.create(name,report["model"],report.get("leave_one_out"),snapshot)

@app.post("/api/models/{model_id}/promote")
def promote_model(model_id:str,payload:dict):
    target=payload.get("target");note=payload.get("note")
    try:return model_registry.promote(model_id,target,note)
    except KeyError:raise HTTPException(status_code=404,detail="model not found")
    except ValueError as e:raise HTTPException(status_code=422,detail=str(e))

@app.get("/api/calibration-lab/status")
def calibration_lab_status():
    records,excluded=_eligible_lab_records()
    out=readiness(records);out["eligible_records"]=[r.__dict__ for r in records];out["excluded"]=excluded
    return out

@app.post("/api/calibration-lab/fit")
def calibration_lab_fit():
    records,excluded=_eligible_lab_records()
    gate=readiness(records)
    if not gate["ready"]:
        raise HTTPException(status_code=422,detail={"message":"calibration readiness gate failed","reasons":gate["reasons"],"excluded":excluded})
    try:return fit_report(records)
    except ValueError as e:raise HTTPException(status_code=422,detail={"message":"model fit failed","reason":str(e)})

@app.put("/api/swatches/{swatch_id}/calibration-metadata")
def calibration_metadata(swatch_id:int, payload:dict):
    if swatch_store.get(swatch_id) is None: raise HTTPException(status_code=404,detail="swatch not found")
    try:return swatch_store.set_calibration_metadata(
      swatch_id,payload.get("replicate_group_id"),payload.get("operator_id"),payload.get("condition","unknown"),
      payload.get("instrument_id"),payload.get("photo_reference"))
    except ValueError as e:raise HTTPException(status_code=422,detail=str(e))

@app.get("/api/swatches")
def list_swatches():
    return swatch_store.list()

@app.get("/api/swatches/{swatch_id}")
def get_swatch(swatch_id:int):
    s=swatch_store.get(swatch_id)
    if s is None: raise HTTPException(status_code=404,detail="swatch not found")
    return s

@app.post("/api/swatches")
def create_swatch(request:SwatchCreateRequest):
    # Verify referenced entities before accepting empirical evidence.
    service._pattern(request.pattern_id,request.pattern_version)
    if service._yarn(request.yarn_id) is None:
        raise HTTPException(status_code=404,detail="yarn not found")
    return swatch_store.create(request.model_dump())

@app.delete("/api/swatches/{swatch_id}")
def delete_swatch(swatch_id:int):
    if not swatch_store.delete(swatch_id):
        raise HTTPException(status_code=404,detail="swatch not found")
    return {"status":"deleted","swatch_id":swatch_id}

@app.get("/api/yarns")
def yarns():
    return service.yarns()


@app.post("/api/calculate")
def calculate(request: CalculationRequest):
    try:
        return service.calculate(request)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
