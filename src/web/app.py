from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import io as _io
from src.storage.backup import build_backup_zip

from .models import CalculationRequest, EditorPatternInput, SavePatternRequest, ProjectCreateRequest, ProjectUpdateRequest, YarnCreateRequest, SwatchCreateRequest, YarnExtraUpdateRequest, SupplierCreateRequest, StashUpsertRequest, CompanySettingsRequest, ProductLineCreateRequest, ProductLineUpdateRequest, ProductMaterialCreateRequest
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
from src.complex_consumption.bridge import calculate_operation_program, UNCALIBRATED_BASELINE_MODEL_ID
from src.gauge_engine.gauge import Gauge
from src.library.yarn_geometry import estimate_yarn_diameter_mm
from src.crochet_calibration.record import CrochetCalibrationRecord
from src.crochet_calibration.protocol import readiness as crochet_calibration_readiness
from src.crochet_calibration.fit import fit_crochet_model
from src.crochet_calibration.store import CrochetCalibrationStore
from src.crochet_calibration.experiment import generate_experiment_plan
from src.crochet_calibration.quality import replicate_quality as crochet_replicate_quality, measurement_consistency
from src.crochet_calibration.audit import dataset_snapshot, calibration_audit
from src.multiyarn.engine import calculate_multiyarn
from src.toy_assembly.bom import aggregate_toy_bom
import datetime, os, sqlite3, time
from collections import defaultdict
from fastapi import Request, Response, Depends
from fastapi.responses import JSONResponse
from .auth import UserStore, SessionSigner, session_secret_from_env, SESSION_COOKIE, SESSION_DAYS

ROOT = Path(__file__).resolve().parents[2]
# All mutable state (sqlite files, session secret) lives under DATA_DIR so a
# persistent volume can be mounted there in production (Railway) and survive deploys.
DATA_DIR = Path(os.environ.get("YARNENGINE_DATA_DIR") or (ROOT / "data/db"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "web_app.sqlite"
STATIC = Path(__file__).resolve().parent / "static"

ensure_demo_database(ROOT, DB_PATH)
model_registry = ModelRegistry(DATA_DIR / 'model_registry.sqlite')
service = WebService(ROOT, DB_PATH, model_registry=model_registry)
project_store = ProjectStore(DATA_DIR / 'projects.sqlite')
swatch_store = SwatchStore(DATA_DIR / 'swatches.sqlite')
crochet_cal_store = CrochetCalibrationStore(DATA_DIR / 'crochet_calibration.sqlite')
operation_map = load_operation_map(ROOT)
user_store = UserStore(DATA_DIR / 'users.sqlite')
user_store.seed_admin_from_env()
session_signer = SessionSigner(session_secret_from_env(DATA_DIR))

app = FastAPI(
    title="Yarn Consumption Engine",
    version="M12.1",
    description="Crochet yarn consumption calculator with a graphical pattern library, uncalibrated geometry baseline and optional calibration.",
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# ---------------------------------------------------------------- auth ---
PUBLIC_PATHS = {"/", "/sw.js", "/manifest.webmanifest", "/api/health", "/api/auth/login",
                "/api/auth/register", "/api/auth/logout", "/api/auth/me", "/api/auth/status"}

def _auth_disabled() -> bool:
    return os.environ.get("YARNENGINE_AUTH_DISABLED") == "1"

def _current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    uid = session_signer.verify(token)
    if uid is None:
        return None
    u = user_store.get(uid)
    if not u or not u["active"]:
        return None
    return UserStore.public(u)

def _current_user_id(request: Request):
    """The signed-in user's id, or None (including whenever auth is disabled,
    e.g. in most tests) -- used to scope per-user data like projects and stash."""
    u = getattr(request.state, "user", None)
    return u["id"] if u else None

def _require_admin(request: Request):
    """Raise 403 unless the signed-in user is an admin. A no-op when auth is
    disabled (e.g. in tests), matching how the rest of the app treats that mode."""
    u = getattr(request.state, "user", None)
    if u is not None and u["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin only")

@app.middleware("http")
async def require_login(request: Request, call_next):
    path = request.url.path
    if (_auth_disabled() or path in PUBLIC_PATHS or path.startswith("/static/")
            or path.startswith("/docs") or path.startswith("/openapi") or path.startswith("/api/share/")):
        return await call_next(request)
    user = _current_user(request)
    if user is None:
        return JSONResponse(status_code=401, content={"detail": "login required"})
    request.state.user = user
    if path.startswith("/api/admin/") and user["role"] != "admin":
        return JSONResponse(status_code=403, content={"detail": "admin only"})
    return await call_next(request)

def _set_session(response: Response, user_id: int):
    secure = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    response.set_cookie(SESSION_COOKIE, session_signer.issue(user_id), max_age=SESSION_DAYS*86400,
                        httponly=True, samesite="lax", secure=secure, path="/")

@app.get("/api/auth/status")
def auth_status():
    return {"registration_open": os.environ.get("YARNENGINE_REGISTRATION", "open") == "open",
            "has_admin": user_store.admin_count() > 0, "auth_disabled": _auth_disabled()}

@app.post("/api/auth/register")
def auth_register(payload: dict, response: Response):
    if os.environ.get("YARNENGINE_REGISTRATION", "open") != "open":
        raise HTTPException(status_code=403, detail="registration is closed")
    try:
        # The very first account becomes administrator if none was seeded from the environment.
        role = "admin" if user_store.count() == 0 else "user"
        u = user_store.create(payload.get("username", ""), payload.get("password", ""), role=role)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    _set_session(response, u["id"])
    return u

# ---------------------------------------------------------- login rate limit ---
# In-memory throttle on failed logins, keyed by username. Simple by design: it
# slows down sustained automated guessing against a known account on a single
# instance and resets on deploy. It does not need to be perfect or shared
# across instances.
#
# Deliberately NOT keyed by client IP: behind Railway's edge proxy,
# request.client.host was observed to vary between requests from the very
# same short curl/PowerShell loop, which would silently defeat an IP-based (or
# IP+username) key -- each attempt would land in its own near-empty bucket and
# never accumulate. Username alone is stable and still meets the audit's own
# "per-IP or per-username throttle" bar.
LOGIN_MAX_ATTEMPTS = 8
LOGIN_WINDOW_SECONDS = 300  # 5 minutes
_login_attempts: dict[str, list[float]] = defaultdict(list)

def _login_rate_limit_key(request: Request, username: str) -> str:
    return (username or "").strip().lower()

def _check_login_rate_limit(request: Request, username: str):
    key = _login_rate_limit_key(request, username)
    now = time.monotonic()
    attempts = _login_attempts[key]
    cutoff = now - LOGIN_WINDOW_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.pop(0)
    if not attempts:
        _login_attempts.pop(key, None)
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        retry_after = max(1, int(LOGIN_WINDOW_SECONDS - (now - attempts[0])))
        raise HTTPException(status_code=429, detail="too many login attempts, try again later",
                            headers={"Retry-After": str(retry_after)})
    # Opportunistically cap unbounded growth from an attacker spraying many
    # distinct usernames -- drop the oldest tracked keys once this gets large.
    if len(_login_attempts) > 5000:
        for stale_key in list(_login_attempts.keys())[:1000]:
            _login_attempts.pop(stale_key, None)

def _record_failed_login(request: Request, username: str):
    _login_attempts[_login_rate_limit_key(request, username)].append(time.monotonic())

@app.post("/api/auth/login")
def auth_login(payload: dict, request: Request, response: Response):
    username = payload.get("username", "")
    _check_login_rate_limit(request, username)
    u = user_store.authenticate(username, payload.get("password", ""))
    if u is None:
        _record_failed_login(request, username)
        raise HTTPException(status_code=401, detail="invalid username or password")
    _login_attempts.pop(_login_rate_limit_key(request, username), None)
    _set_session(response, u["id"])
    return u

@app.post("/api/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"status": "logged_out"}

@app.get("/api/auth/me")
def auth_me(request: Request):
    u = _current_user(request)
    if u is None:
        raise HTTPException(status_code=401, detail="login required")
    return u

@app.post("/api/auth/change-password")
def auth_change_password(payload: dict, request: Request):
    u = request.state.user
    if not user_store.authenticate(u["username"], payload.get("current_password", "")):
        raise HTTPException(status_code=401, detail="current password incorrect")
    try:
        user_store.set_password(u["id"], payload.get("new_password", ""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "ok"}

@app.get("/api/admin/users")
def admin_users():
    return user_store.list()

@app.post("/api/admin/users")
def admin_create_user(payload: dict):
    try:
        return user_store.create(payload.get("username", ""), payload.get("password", ""),
                                 role=payload.get("role", "user"), active=bool(payload.get("active", True)))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.put("/api/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: dict, request: Request):
    target = user_store.get(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    me = request.state.user
    try:
        if "active" in payload:
            if user_id == me["id"] and not payload["active"]:
                raise ValueError("you cannot deactivate your own account")
            user_store.set_active(user_id, bool(payload["active"]))
        if "role" in payload:
            if user_id == me["id"] and payload["role"] != "admin":
                raise ValueError("you cannot remove your own admin role")
            user_store.set_role(user_id, payload["role"])
        if payload.get("password"):
            user_store.set_password(user_id, payload["password"])
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return UserStore.public(user_store.get(user_id))

@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request):
    if user_id == request.state.user["id"]:
        raise HTTPException(status_code=422, detail="you cannot delete your own account")
    if not user_store.delete(user_id):
        raise HTTPException(status_code=404, detail="user not found")
    return {"status": "deleted", "user_id": user_id}

@app.get("/api/admin/backup")
def admin_backup():
    """Download a consistent zip snapshot of every database file (users, yarns,
    product lines, projects, swatches, calibration data) for offline safekeeping.
    The persistent volume is still the primary store; this is a manual, on-demand
    second copy against volume loss or corruption."""
    data = build_backup_zip(DATA_DIR)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"yarnengine-backup-{stamp}.zip"
    return StreamingResponse(_io.BytesIO(data), media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


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
    return {"status": "ok", "version": "M12.1"}


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
def crochet_calibration_delete(record_id:str, request:Request):
    _require_admin(request)
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
    yarn=service._yarn(payload.get("yarn_id")) if payload.get("yarn_id") else None
    diameter,diameter_source,diameter_warnings=estimate_yarn_diameter_mm(yarn,payload.get("yarn_diameter_mm"))
    if diameter is None:
        raise HTTPException(status_code=422,detail="yarn diameter is required (select a yarn with diameter/WPI/weight/tex or pass yarn_diameter_mm)")
    gauge=Gauge(float(payload["gauge_stitches_per_10cm"]),float(payload["gauge_rows_per_10cm"]),100.0,100.0)
    try:
        calc,pred,audit=calculate_operation_program(
            record=production,operation_counts=analysed["operation_counts"],gauge=gauge,
            yarn_diameter_mm=float(diameter),allowance_percent=float(payload.get("allowance_percent",0)),
            tex=(yarn.get("tex") if yarn else None),package_length_m=(yarn.get("package_length_m") if yarn else None),
            domain_policy=payload.get("domain_policy","strict"),source=kind,
            hook_mm=(float(payload["hook_mm"]) if payload.get("hook_mm") else None),
            cyc_weight=(yarn.get("cyc_weight") if yarn else None))
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e))
    return {"program_type":kind,"program_analysis":analysed,"calculation":calc.__dict__,
            "prediction":{"estimate_m":pred.estimate_m,"lower_95_m":pred.lower_95_m,"upper_95_m":pred.upper_95_m,"in_domain":pred.in_domain,"warnings":pred.warnings},
            "audit":{**audit,"yarn_diameter_mm":diameter,"yarn_diameter_source":diameter_source,"yarn_diameter_warnings":list(diameter_warnings)},
            "model_id":production["model_id"] if production else UNCALIBRATED_BASELINE_MODEL_ID}

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


@app.get("/api/patterns/full")
def patterns_full():
    """Every active pattern with its repeat grid, for the graphical pattern library."""
    store=service._store()
    try:
        rows=store.conn.execute("SELECT pattern_id,version,name,family_id,difficulty,tags_json,techniques_json,pattern_json FROM patterns WHERE active=1").fetchall()
        out=[]
        for r in rows:
            p=json.loads(r["pattern_json"])
            out.append({"pattern_id":r["pattern_id"],"version":r["version"],"name":r["name"],"family_id":r["family_id"],
                        "difficulty":r["difficulty"],"tags":json.loads(r["tags_json"]),"techniques":json.loads(r["techniques_json"]),
                        "repeat":p.get("repeat"),"rows":p.get("rows")})
        return sorted(out,key=lambda x:(x["family_id"],x["name"],x["version"]))
    finally:
        store.close()


@app.get("/api/amigurumi/constructions")
def amigurumi_constructions(category: str | None = None, text: str | None = None, limit: int = 500):
    if limit < 1 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 5000")
    path = ROOT / "data/library/amigurumi_construction_catalog.json"
    if not path.exists():
        return {"count": 0, "items": []}
    records = json.loads(path.read_text(encoding="utf-8"))["records"]
    if category:
        records = [x for x in records if x.get("category", "").lower() == category.lower()]
    if text:
        q = text.lower()
        records = [x for x in records if q in " ".join([x.get("canonical_name", ""), x.get("category", ""), *x.get("aliases", []), *x.get("typical_use", [])]).lower()]
    return {"count": len(records), "items": records[:limit]}


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


def _owned_project_or_404(project_id:int, http_request:Request):
    p=project_store.get(project_id)
    if p is None or p.get("user_id")!=_current_user_id(http_request):
        raise HTTPException(status_code=404,detail="project not found")
    return p

@app.get("/api/projects")
def list_projects(http_request:Request):
    return project_store.list(user_id=_current_user_id(http_request))

@app.get("/api/projects/{project_id}")
def get_project(project_id:int, http_request:Request):
    return _owned_project_or_404(project_id, http_request)

@app.post("/api/projects")
def create_project(request: ProjectCreateRequest, http_request:Request):
    calc=request.calculation.model_dump()
    return project_store.create(
      name=request.name,
      description=request.description,
      pattern_id=calc["pattern_id"],
      pattern_version=calc["pattern_version"],
      yarn_id=calc.get("yarn_id"),
      request=calc,
      result=request.result,
      status=request.status,
      user_id=_current_user_id(http_request),
    )

@app.put("/api/projects/{project_id}")
def update_project(project_id:int, request:ProjectUpdateRequest, http_request:Request):
    _owned_project_or_404(project_id, http_request)
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
def calculate_project(project_id:int, http_request:Request):
    p=_owned_project_or_404(project_id, http_request)
    try:
        req=CalculationRequest(**p["request"])
        result=service.calculate(req, user_id=_current_user_id(http_request))
    except (ValueError,KeyError) as e:
        raise HTTPException(status_code=422,detail=str(e))
    return project_store.update(project_id,result=result,status="calculated")

@app.delete("/api/projects/{project_id}")
def delete_project(project_id:int, http_request:Request):
    _owned_project_or_404(project_id, http_request)
    project_store.delete(project_id)
    return {"status":"deleted","project_id":project_id}

@app.post("/api/projects/{project_id}/share")
def share_project(project_id:int, http_request:Request):
    _owned_project_or_404(project_id, http_request)
    p=project_store.set_share_token(project_id)
    return {"share_token":p["share_token"]}

@app.delete("/api/projects/{project_id}/share")
def unshare_project(project_id:int, http_request:Request):
    _owned_project_or_404(project_id, http_request)
    p=project_store.set_share_token(project_id, token=False)
    return {"status":"unshared"}

@app.get("/api/share/{token}")
def get_shared_project(token:str):
    """Public, read-only view of a project someone chose to share -- no login required."""
    p=project_store.get_by_share_token(token)
    if p is None:
        raise HTTPException(status_code=404,detail="shared project not found")
    return {"name":p["name"],"description":p["description"],"request":p["request"],
            "result":p["result"],"status":p["status"],"updated_at":p["updated_at"]}

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


@app.patch("/api/yarns/{yarn_id}")
def update_yarn_extra(yarn_id:str, request:YarnExtraUpdateRequest):
    """Collaborative fields (description, photo, product line, indicative price) any
    signed-in user may keep current -- unlike the sourced technical fields, which stay
    fixed once imported. Admin-only deletion still protects the yarn record itself."""
    fields={k:v for k,v in request.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=422,detail="no fields to update")
    store=service._store()
    try:
        updated=store.update_yarn_extra(yarn_id,**fields)
    finally: store.close()
    if updated is None:
        raise HTTPException(status_code=404,detail="yarn not found")
    return updated

@app.get("/api/yarns/{yarn_id}/suppliers")
def list_yarn_suppliers(yarn_id:str):
    store=service._store()
    try:
        if store.get_yarn(yarn_id) is None:
            raise HTTPException(status_code=404,detail="yarn not found")
        return store.list_suppliers(yarn_id)
    finally: store.close()

@app.post("/api/yarns/{yarn_id}/suppliers")
def add_yarn_supplier(yarn_id:str, request:SupplierCreateRequest):
    store=service._store()
    try:
        if store.get_yarn(yarn_id) is None:
            raise HTTPException(status_code=404,detail="yarn not found")
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        return store.add_supplier(yarn_id,request.name,request.price_amount,request.price_currency,
                                   request.product_url,request.notes,now)
    finally: store.close()

@app.delete("/api/admin/yarns/{yarn_id}/suppliers/{supplier_id}")
def delete_yarn_supplier(yarn_id:str, supplier_id:int):
    store=service._store()
    try:
        if not store.delete_supplier(yarn_id,supplier_id):
            raise HTTPException(status_code=404,detail="supplier not found")
    finally: store.close()
    return {"status":"deleted","supplier_id":supplier_id}


# ------------------------------------------------------------- product lines (catalogue) ---
@app.get("/api/product-lines")
def list_product_lines():
    store=service._store()
    try: return store.list_product_lines()
    finally: store.close()

@app.post("/api/admin/product-lines")
def create_product_line(request:ProductLineCreateRequest):
    store=service._store()
    try:
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            return store.create_product_line(request.name,request.description,request.photo_url,
                                               request.product_url,now)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409,detail="a product line with this name already exists")
    finally: store.close()

@app.patch("/api/admin/product-lines/{line_id}")
def update_product_line(line_id:int, request:ProductLineUpdateRequest):
    store=service._store()
    try:
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        data=request.model_dump(exclude_unset=True)
        try:
            updated=store.update_product_line(line_id,now,**data)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409,detail="a product line with this name already exists")
        if updated is None:
            raise HTTPException(status_code=404,detail="product line not found")
        return updated
    finally: store.close()

@app.delete("/api/admin/product-lines/{line_id}")
def delete_product_line(line_id:int):
    store=service._store()
    try:
        if not store.delete_product_line(line_id):
            raise HTTPException(status_code=404,detail="product line not found")
    finally: store.close()
    return {"status":"deleted","id":line_id}

@app.post("/api/admin/product-lines/{line_id}/materials")
def add_product_material(line_id:int, request:ProductMaterialCreateRequest):
    store=service._store()
    try:
        if store.get_product_line(line_id) is None:
            raise HTTPException(status_code=404,detail="product line not found")
        if store.get_yarn(request.yarn_id) is None:
            raise HTTPException(status_code=422,detail="yarn not found")
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        store.add_material(line_id,request.yarn_id,request.length_m,request.quantity_g,request.notes,now)
        return store.get_product_line(line_id)
    finally: store.close()

@app.delete("/api/admin/product-lines/{line_id}/materials/{material_id}")
def delete_product_material(line_id:int, material_id:int):
    store=service._store()
    try:
        if not store.delete_material(line_id,material_id):
            raise HTTPException(status_code=404,detail="material not found")
        return store.get_product_line(line_id)
    finally: store.close()


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
def delete_swatch(swatch_id:int, request:Request):
    _require_admin(request)
    if not swatch_store.delete(swatch_id):
        raise HTTPException(status_code=404,detail="swatch not found")
    return {"status":"deleted","swatch_id":swatch_id}

@app.get("/api/yarns")
def yarns():
    return service.yarns()


@app.delete("/api/admin/yarns/{yarn_id}")
def admin_delete_yarn(yarn_id: str):
    store = service._store()
    try:
        if not store.delete_yarn(yarn_id):
            raise HTTPException(status_code=404, detail="yarn not found")
    finally:
        store.close()
    return {"status": "deleted", "yarn_id": yarn_id}


# ------------------------------------------------------------- yarn stash ---
@app.get("/api/stash")
def list_stash(http_request:Request):
    store=service._store()
    try:
        return store.list_stash(_current_user_id(http_request))
    finally: store.close()

@app.post("/api/stash")
def upsert_stash(request:StashUpsertRequest, http_request:Request):
    store=service._store()
    try:
        if store.get_yarn(request.yarn_id) is None:
            raise HTTPException(status_code=404,detail="yarn not found")
        now=datetime.datetime.now(datetime.timezone.utc).isoformat()
        return store.upsert_stash(_current_user_id(http_request),request.yarn_id,
                                   request.quantity_g,request.quantity_skeins,request.notes,now)
    finally: store.close()

@app.delete("/api/stash/{yarn_id}")
def delete_stash(yarn_id:str, http_request:Request):
    store=service._store()
    try:
        if not store.delete_stash(_current_user_id(http_request),yarn_id):
            raise HTTPException(status_code=404,detail="stash entry not found")
    finally: store.close()
    return {"status":"deleted","yarn_id":yarn_id}


# --------------------------------------------------------- company/branding ---
_COMPANY_FIELDS=("company_name","address","company_number","vat_number","email","phone","website")

@app.get("/api/settings/company")
def get_company_settings():
    store=service._store()
    try:
        settings=store.all_settings()
    finally: store.close()
    return {f:settings.get(f"company.{f}","") for f in _COMPANY_FIELDS}

@app.put("/api/admin/settings/company")
def update_company_settings(request:CompanySettingsRequest):
    store=service._store()
    try:
        data=request.model_dump()
        for f in _COMPANY_FIELDS:
            if data.get(f) is not None:
                store.set_setting(f"company.{f}",data[f])
        settings=store.all_settings()
    finally: store.close()
    return {f:settings.get(f"company.{f}","") for f in _COMPANY_FIELDS}


@app.post("/api/calculate")
def calculate(request: CalculationRequest, http_request: Request):
    try:
        return service.calculate(request, user_id=_current_user_id(http_request))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
