from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import io as _io
from src.storage.backup import build_backup_zip
from src.storage.sqlite_store import SQLiteStore
from src.yarn_ingestion.store import IngestionStore
from src.yarn_ingestion.registry import load_registry
from src.yarn_ingestion.seed import import_seed_jsonl

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
import json, re, math
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
import base64
from src.design.parts import build_design, written_pattern, round_text, OP_WORDS
from src.design.shapes import ARCHETYPES as DESIGN_ARCHETYPES
from src.pattern_import.crochet_rounds import (parse_pattern as parse_crochet_rounds,
                                               parse_round as parse_one_round,
                                               _vocabulary as crochet_vocabulary,
                                               ROUND_HEADER)
from src.design.vision import (describe_photo, transcribe_pattern, configured as vision_configured,
                               model_name as vision_model_name, env_key as vision_env_key,
                               mask_key as vision_mask_key, DEFAULT_MODEL as VISION_DEFAULT_MODEL,
                               VisionUnavailable, CATEGORIES as VISION_CATEGORIES)
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
from src.crochet_geometry.stitch_loop import (operation_length_mm, OPERATION_WRAPS,
                                              OPERATION_WRAP_RATIO)
from src.library.colours import match_colour
from src.colour.harmony import SCHEMES as COLOUR_SCHEMES, build_palette
from src.construction import types as constructions
from src.web.plain import problem as plain_problem
from src.crochet import terms as crochet_terms
from src.beginner import plans as beginner
from src.tools import maths as tool_maths
from src.tools.pricing import price_piece
from src.worklog.store import WorkLogStore
import datetime, os, sqlite3, time
from collections import defaultdict
from fastapi import Request, Response, Depends
from fastapi.responses import JSONResponse
from .auth import UserStore, SessionSigner, session_secret_from_env, SESSION_COOKIE, SESSION_DAYS, RESET_TOKEN_TTL_MINUTES
from .mailer import send_email

ROOT = Path(__file__).resolve().parents[2]
# All mutable state (sqlite files, session secret) lives under DATA_DIR so a
# persistent volume can be mounted there in production (Railway) and survive deploys.
DATA_DIR = Path(os.environ.get("YARNENGINE_DATA_DIR") or (ROOT / "data/db"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "web_app.sqlite"
STATIC = Path(__file__).resolve().parent / "static"

ensure_demo_database(ROOT, DB_PATH)


def _sync_ingestion_registry():
    """Register the M9 manufacturer-source list in the ingestion tables on every
    startup, the same idempotent upsert pattern ensure_demo_database uses for
    patterns/yarns -- adding a source to sources.json makes it show up without
    any manual step."""
    registry_path = ROOT / "data/ingestion/sources.json"
    seed_path = ROOT / "data/ingestion/seed_current_products_v0_5.jsonl"
    if not registry_path.exists():
        return
    core = SQLiteStore(DB_PATH)
    try:
        ingestion = IngestionStore(core)
        for source in load_registry(registry_path):
            ingestion.upsert_source(source)
        # The 296-row v0.5 reference set: the ~101 complete rows are also
        # shipped as data/yarns/*.json (so they go through the same validated
        # bulk_import_yarns path as every other library yarn); re-running this
        # here is what keeps the reference/review table itself in sync, and is
        # a harmless idempotent upsert for the yarn rows it touches too.
        if seed_path.exists():
            import_seed_jsonl(ingestion, seed_path)
    finally:
        core.close()


_sync_ingestion_registry()
model_registry = ModelRegistry(DATA_DIR / 'model_registry.sqlite')
service = WebService(ROOT, DB_PATH, model_registry=model_registry)
project_store = ProjectStore(DATA_DIR / 'projects.sqlite')
swatch_store = SwatchStore(DATA_DIR / 'swatches.sqlite')
worklog_store = WorkLogStore(DATA_DIR / 'worklog.sqlite')
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
                "/api/auth/register", "/api/auth/logout", "/api/auth/me", "/api/auth/status",
                "/api/auth/forgot-password", "/api/auth/reset-password"}

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

@app.middleware("http")
async def no_stale_app_shell(request: Request, call_next):
    """Browsers were keeping old copies of the app after deploys (no Cache-Control
    was sent, so heuristic caching applied). no-cache still allows caching but
    forces revalidation against the ETag on every load, so a reload always picks
    up the newly deployed version."""
    response = await call_next(request)
    path = request.url.path
    if path in ("/", "/sw.js", "/manifest.webmanifest") or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response

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

@app.put("/api/auth/email")
def auth_update_email(payload: dict, request: Request):
    u = request.state.user
    try:
        user_store.set_email(u["id"], payload.get("email", ""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return UserStore.public(user_store.get(u["id"]))

# ---------------------------------------------------------- password reset ---
# In-memory throttle on reset requests, keyed the same way as the login
# limiter above (by identifier, not client IP -- see that comment for why).
RESET_MAX_ATTEMPTS = 4
RESET_WINDOW_SECONDS = 600  # 10 minutes
_reset_attempts: dict[str, list[float]] = defaultdict(list)

def _reset_rate_limit_key(identifier: str) -> str:
    return (identifier or "").strip().lower()

def _check_reset_rate_limit(identifier: str):
    key = _reset_rate_limit_key(identifier)
    now = time.monotonic()
    attempts = _reset_attempts[key]
    cutoff = now - RESET_WINDOW_SECONDS
    while attempts and attempts[0] < cutoff:
        attempts.pop(0)
    if not attempts:
        _reset_attempts.pop(key, None)
    if len(attempts) >= RESET_MAX_ATTEMPTS:
        retry_after = max(1, int(RESET_WINDOW_SECONDS - (now - attempts[0])))
        raise HTTPException(status_code=429, detail="too many requests, try again later",
                            headers={"Retry-After": str(retry_after)})
    if len(_reset_attempts) > 5000:
        for stale_key in list(_reset_attempts.keys())[:1000]:
            _reset_attempts.pop(stale_key, None)

def _record_reset_attempt(identifier: str):
    _reset_attempts[_reset_rate_limit_key(identifier)].append(time.monotonic())

@app.post("/api/auth/forgot-password")
def auth_forgot_password(payload: dict, request: Request):
    identifier = (payload.get("username_or_email") or payload.get("username") or payload.get("email") or "").strip()
    _check_reset_rate_limit(identifier)
    _record_reset_attempt(identifier)
    user = None
    if identifier:
        user = user_store.get_by_username(identifier)
        if user is None and "@" in identifier:
            user = user_store.get_by_email(identifier)
    if user and user.get("active") and user.get("email"):
        token = user_store.create_password_reset(user["id"])
        reset_link = f"{str(request.base_url).rstrip('/')}/?reset_token={token}"
        try:
            send_email(
                to=user["email"],
                subject="Reset your YarnEngine password",
                html=(f"<p>Someone asked to reset the password for the YarnEngine account "
                      f"<b>{user['username']}</b>.</p>"
                      f"<p><a href=\"{reset_link}\">Click here to set a new password</a>. "
                      f"This link expires in {RESET_TOKEN_TTL_MINUTES} minutes.</p>"
                      f"<p>If you didn't request this, you can safely ignore this email.</p>"),
                text=(f"Reset your YarnEngine password: {reset_link} "
                      f"(expires in {RESET_TOKEN_TTL_MINUTES} minutes). "
                      f"If you didn't request this, ignore this email."),
            )
        except Exception:
            pass  # best-effort; never let a send failure leak through to the caller
    # Always the same response whether or not an account/email was found or
    # the send actually succeeded, so this endpoint can't be used to probe
    # which usernames/emails exist.
    return {"status": "ok"}

@app.post("/api/auth/reset-password")
def auth_reset_password(payload: dict, response: Response):
    token = payload.get("token") or ""
    new_password = payload.get("new_password") or ""
    try:
        user = user_store.consume_password_reset(token, new_password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if user is None:
        raise HTTPException(status_code=400, detail="invalid or expired reset link")
    _set_session(response, user["id"])
    return user

@app.get("/api/admin/users")
def admin_users():
    return user_store.list()

@app.post("/api/admin/users")
def admin_create_user(payload: dict):
    try:
        return user_store.create(payload.get("username", ""), payload.get("password", ""),
                                 role=payload.get("role", "user"), active=bool(payload.get("active", True)),
                                 email=payload.get("email") or None)
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
        if "email" in payload:
            user_store.set_email(user_id, payload["email"])
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


@app.get("/api/admin/ingestion/stats")
def admin_ingestion_stats():
    """Read-only status of the M9 automated yarn-catalogue ingestion pipeline:
    how many manufacturer sources are registered/verified, how many reference
    products are on file, and how many yarns currently in the live catalogue
    came from this pipeline (vs. the original hand-curated library)."""
    store = service._store()
    try:
        ingestion = IngestionStore(store)
        stats = ingestion.stats()
        registry_path = ROOT / "data/ingestion/sources.json"
        sources = load_registry(registry_path) if registry_path.exists() else []
        web_ingested = store.conn.execute(
            "SELECT COUNT(*) FROM yarns WHERE source_type IN ('official_web_seed','official_web')"
        ).fetchone()[0]
        return {
            **stats,
            "sources_verified": sum(1 for s in sources if s.domain_status == "verified"),
            "sources_needing_verification": sum(1 for s in sources if s.domain_status != "verified"),
            "web_ingested_yarns": web_ingested,
        }
    finally:
        store.close()


@app.get("/api/admin/ingestion/review")
def admin_ingestion_review(limit: int = 100):
    store = service._store()
    try:
        ingestion = IngestionStore(store)
        rows = ingestion.conn.execute("""
          SELECT q.id,q.status,q.reason,q.created_at,c.source_id,c.brand,c.product_name,c.source_url,c.confidence
          FROM manual_review_queue q JOIN product_candidates c ON c.candidate_id=q.candidate_id
          WHERE q.status='open' ORDER BY q.created_at LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        store.close()


VISION_KEY_SETTING = "secret.anthropic_api_key"   # "secret." keeps it out of backups
VISION_MODEL_SETTING = "vision.model"

def _vision_settings() -> tuple[str, str]:
    """(api key, model) as configured in the app, empty when not set."""
    store = service._store()
    try:
        return (store.get_setting(VISION_KEY_SETTING, "") or "",
                store.get_setting(VISION_MODEL_SETTING, "") or "")
    finally:
        store.close()


def _cost_design_in_yarn(design: dict, payload: dict) -> None:
    """Work out yarn length and weight for every part, and for the whole thing.

    Uses exactly the same engine as the single-piece calculator, once per part,
    multiplied by how many of that part are needed -- so the totals and the
    per-part figures can never drift apart from what the calculator would say
    for the same piece.
    """
    yarn = service._yarn(payload.get("yarn_id")) if payload.get("yarn_id") else None
    diameter, diameter_source, diameter_warnings = estimate_yarn_diameter_mm(
        yarn, payload.get("yarn_diameter_mm"))
    if diameter is None:
        design["yarn"] = {"available": False,
                          "reason": "choose a yarn (or enter a yarn diameter) to get length and weight",
                          "warnings": list(diameter_warnings)}
        return
    gauge = Gauge(float(design["gauge_stitches_per_10cm"]),
                  float(design["gauge_rows_per_10cm"]), 100.0, 100.0)
    production = model_registry.production()
    package_length = yarn.get("package_length_m") if yarn else None
    total_len = total_mass = 0.0
    warnings: list[str] = list(diameter_warnings)
    mass_known = True
    for part in design["parts"]:
        analysed = analyse_rounds({"initial_stitches": part["initial_stitches"],
                                   "rounds": part["rounds"]}, service.operations)
        if not analysed.get("valid"):
            raise HTTPException(status_code=500,
                                detail={**plain_problem(analysed["issues"]),
                                        "part": part["name"]})
        try:
            calc, pred, _audit = calculate_operation_program(
                record=production, operation_counts=analysed["operation_counts"], gauge=gauge,
                yarn_diameter_mm=float(diameter),
                allowance_percent=float(payload.get("allowance_percent", 10) or 0),
                tex=(yarn.get("tex") if yarn else None), package_length_m=package_length,
                domain_policy="warn", source="amigurumi",
                hook_mm=(float(payload["hook_mm"]) if payload.get("hook_mm") else None),
                cyc_weight=(yarn.get("cyc_weight") if yarn else None))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        # Round once, at the figure a person reads, and build every larger
        # figure out of those -- otherwise "1.9 g each" for two pieces sits
        # next to a 3.9 g total and the whole table stops being believable.
        each_len = round(float(calc.recommended_length_m), 2)
        each_mass = round(float(calc.mass_g), 1) if calc.mass_g is not None else None
        if each_mass is None:
            mass_known = False
        part["yarn"] = {
            "length_m_each": each_len,
            "length_m_total": round(each_len * part["copies"], 2),
            "mass_g_each": each_mass,
            "mass_g_total": round(each_mass * part["copies"], 1) if each_mass is not None else None,
            "lower_95_m_each": round(float(pred.lower_95_m), 2),
            "upper_95_m_each": round(float(pred.upper_95_m), 2),
        }
        total_len += part["yarn"]["length_m_total"]
        if each_mass is not None:
            total_mass += part["yarn"]["mass_g_total"]
        for w in (pred.warnings or []):
            if w not in warnings:
                warnings.append(w)
    packages = math.ceil(total_len / package_length) if package_length else None
    design["yarn"] = {
        "available": True,
        "yarn_id": (yarn.get("yarn_id") if yarn else None),
        "yarn_name": (" ".join(x for x in [yarn.get("brand"), yarn.get("product")] if x)
                      if yarn else None),
        "length_m": round(total_len, 2),
        "mass_g": round(total_mass, 1) if mass_known and total_mass else None,
        "packages": packages,
        "package_length_m": package_length,
        "allowance_percent": float(payload.get("allowance_percent", 10) or 0),
        "yarn_diameter_mm": diameter,
        "yarn_diameter_source": diameter_source,
        # Shown on screen so a weight that looks wrong can be checked by hand:
        # grams = metres x g_per_m, and nothing else.
        "tex": (yarn.get("tex") if yarn else None),
        "g_per_m": (round(float(yarn["tex"]) / 1000.0, 4)
                    if yarn and yarn.get("tex") else None),
        "package_mass_g": (yarn.get("package_mass_g") if yarn else None),
        "model_id": production["model_id"] if production else UNCALIBRATED_BASELINE_MODEL_ID,
        "warnings": warnings,
    }


@app.get("/api/design/status")
def design_status():
    """Whether photo analysis is available on this server."""
    key, model = _vision_settings()
    return {"vision_configured": vision_configured(key), "model": vision_model_name(model),
            "key_source": ("app" if key else ("env" if vision_env_key() else None)),
            "archetypes": DESIGN_ARCHETYPES, "categories": VISION_CATEGORIES}


@app.get("/api/admin/settings/vision")
def get_vision_settings():
    """Admin view of the photo-reading credentials.

    Never returns the key itself -- only whether one is set, where it came
    from, and enough of it to recognise which key it is.
    """
    key, model = _vision_settings()
    return {"configured": vision_configured(key),
            "key_source": ("app" if key else ("env" if vision_env_key() else None)),
            "key_hint": vision_mask_key(key) if key else vision_mask_key(vision_env_key()),
            "model": model, "effective_model": vision_model_name(model),
            "default_model": VISION_DEFAULT_MODEL}


@app.put("/api/admin/settings/vision")
def update_vision_settings(payload: dict):
    """Store (or clear) the API key used to read photos.

    An empty api_key clears the stored one, falling back to the environment
    variable if the server has one.
    """
    key = payload.get("api_key")
    model = payload.get("model")
    store = service._store()
    try:
        if key is not None:
            cleaned = str(key).strip()
            if cleaned and (len(cleaned) < 20 or " " in cleaned):
                raise HTTPException(status_code=422, detail="that does not look like an API key")
            store.set_setting(VISION_KEY_SETTING, cleaned)
        if model is not None:
            store.set_setting(VISION_MODEL_SETTING, str(model).strip())
        stored_key = store.get_setting(VISION_KEY_SETTING, "") or ""
        stored_model = store.get_setting(VISION_MODEL_SETTING, "") or ""
    finally:
        store.close()
    return {"configured": vision_configured(stored_key),
            "key_source": ("app" if stored_key else ("env" if vision_env_key() else None)),
            "key_hint": vision_mask_key(stored_key) if stored_key else vision_mask_key(vision_env_key()),
            "model": stored_model, "effective_model": vision_model_name(stored_model),
            "default_model": VISION_DEFAULT_MODEL}


@app.post("/api/admin/settings/vision/test")
def test_vision_settings():
    """Check the stored key actually works, with one tiny real request."""
    key, model = _vision_settings()
    if not vision_configured(key):
        raise HTTPException(status_code=422, detail="no API key is set yet")
    import base64 as _b64
    pixel = _b64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    try:
        describe_photo([("image/png", pixel)], hint="single plain ball",
                       api_key=key, model=model, timeout=30)
    except VisionUnavailable as e:
        msg = str(e)
        # Being told "there is nothing recognisable in this 1px image" means the
        # credentials and the model are fine, which is what is being tested.
        if "no usable parts" in msg or "did not return" in msg or "could not read" in msg:
            return {"ok": True, "detail": "The key works — the vision model answered.",
                    "model": vision_model_name(model)}
        raise HTTPException(status_code=502, detail=msg)
    return {"ok": True, "detail": "The key works — the vision model answered.",
            "model": vision_model_name(model)}


# ---------------------------------------------------------------- colours ----
def _colours(yarn_id: str | None = None) -> list[dict]:
    store = service._store()
    try:
        return store.list_colours(yarn_id)
    finally:
        store.close()


def _colour(colour_id: str | None) -> dict | None:
    if not colour_id:
        return None
    store = service._store()
    try:
        return store.get_colour(colour_id)
    finally:
        store.close()


def _public_colour(row: dict | None) -> dict | None:
    if not row:
        return None
    return {"colour_id": row["colour_id"], "name": row["name"], "hex": row["hex"],
            "code": row["code"], "family": row.get("family"),
            "yarn_specific": row.get("yarn_id") is not None,
            "source_type": row.get("source_type")}


@app.get("/api/colours")
def list_colours(yarn_id: str | None = None):
    """Every shade that may be chosen, for this yarn or in general.

    Colour is never typed in anywhere in the app: a pattern's colour is one of
    these rows. A yarn whose own shade card has been captured lists those first
    (``yarn_specific``); everything else falls back to the generic palette.
    """
    rows = [_public_colour(r) for r in _colours(yarn_id)]
    return {"yarn_id": yarn_id, "colours": rows,
            "yarn_specific_count": sum(1 for r in rows if r["yarn_specific"])}


@app.get("/api/colours/schemes")
def colour_schemes():
    """The schemes on offer, and what each one is for."""
    return {"schemes": [{"id": key, "name": spec["name"], "about": spec["about"]}
                        for key, spec in COLOUR_SCHEMES.items()],
            "scopes": [
                {"id": "yarn", "name": "This yarn's own shade card",
                 "about": "One yarn line, so every colour behaves the same in the piece."},
                {"id": "brand", "name": "Anything by this maker",
                 "about": "Wider choice, but check the weights match before mixing."},
                {"id": "stash", "name": "Only yarns in my stash",
                 "about": "Schemes you can start today without ordering anything."},
                {"id": "library", "name": "Every shade card in the library",
                 "about": "The widest choice; the yarns may be very different from each other."}]}


@app.get("/api/colours/palette")
def colour_palette(colour_id: str, scheme: str = "complementary", scope: str = "yarn",
                   count: int = 3, http_request: Request = None):
    """A colour scheme around one real shade, made only of other real shades.

    Nothing here is invented: the wheel decides where a companion should sit,
    and the nearest shade from a manufacturer's own card is what comes back,
    with how far it falls from that ideal. A scheme that cannot be bought is
    worse than no scheme.
    """
    if scheme not in COLOUR_SCHEMES:
        raise HTTPException(status_code=422, detail=f"scheme must be one of {sorted(COLOUR_SCHEMES)}")
    if scope not in ("yarn", "brand", "stash", "library"):
        raise HTTPException(status_code=422, detail="scope must be yarn, brand, stash or library")
    store = service._store()
    try:
        base = store.get_colour(colour_id)
        if base is None:
            raise HTTPException(status_code=404, detail="no such shade")
        if not base.get("yarn_id"):
            raise HTTPException(status_code=422, detail=(
                "that is a shade from the generic palette, not a manufacturer's card — "
                "pick a yarn whose shade card has been captured, so the scheme is made of "
                "colours that can actually be bought"))
        yarn = store.get_yarn(base["yarn_id"]) or {}
        candidates = store.shade_candidates(
            scope=scope, yarn_id=base["yarn_id"], brand=yarn.get("brand"),
            user_id=_current_user_id(http_request) if http_request is not None else None)
        base = {**base, "brand": yarn.get("brand"), "product": yarn.get("product")}
    finally:
        store.close()
    if not candidates:
        raise HTTPException(status_code=422, detail=(
            "there are no shade cards to choose from in that scope — with “only yarns in my "
            "stash”, add a yarn whose shades are known to your stash first"))
    result = build_palette(base, candidates, scheme=scheme, count=count)
    result["scope"] = scope
    result["candidate_count"] = len(candidates)
    result["from"] = ("this yarn's card" if scope == "yarn"
                      else f"{len(candidates)} real shades in scope")
    return result


def _assign_colours(design: dict, payload: dict, described: dict | None = None) -> None:
    """Give the design, and every part, a colour that is a catalogue row.

    A colour the user picked wins outright. Otherwise the description read from
    the photo is *matched* against the catalogue -- the app never stores a
    colour that is not one of these rows, so the picker can always show it
    selected and the user can always change it to another catalogue entry.
    """
    catalogue = _colours(payload.get("yarn_id"))
    chosen = _colour(payload.get("colour_id"))
    if payload.get("colour_id") and chosen is None:
        raise HTTPException(status_code=422, detail="unknown colour_id")
    by_part = {p.get("name"): p.get("colour") for p in ((described or {}).get("parts") or [])}
    for part in design["parts"]:
        matched = chosen or match_colour(by_part.get(part["name"]), catalogue)
        part["colour"] = _public_colour(matched)
        part["colour_source"] = ("chosen" if chosen else
                                 ("matched from the photo" if matched else None))
    main = chosen or next((_colour(p["colour"]["colour_id"]) for p in design["parts"]
                           if p.get("colour")), None)
    design["colour"] = _public_colour(main)
    design["colour_source"] = ("chosen" if chosen else
                               ("matched from the photo" if main else "not set"))
    design["colour_catalogue_size"] = len(catalogue)


# --------------------------------------------------------------- work log ----
def _log_calculation(http_request, kind, title, payload, result, **fields):
    """Write a finished calculation into the person's log.

    Recording must never cost someone the result they just waited for, so every
    failure here is swallowed: a missing log entry is a nuisance, a 500 on a
    calculation that actually succeeded is not.
    """
    try:
        return worklog_store.record(
            user_id=_current_user_id(http_request), kind=kind, title=title,
            request=payload, result=result, **fields)
    except Exception:            # noqa: BLE001 - see the docstring
        import os
        import traceback
        if os.getenv("YARNENGINE_DEBUG_LOG"):
            traceback.print_exc()     # a swallowed failure is still findable
        return None


def _colour_fields(colour: dict | None) -> dict:
    if not colour:
        return {}
    return {"colour_id": colour.get("colour_id"), "colour_name": colour.get("name"),
            "colour_hex": colour.get("hex")}


def _yarn_fields(yarn_id: str | None) -> dict:
    if not yarn_id:
        return {}
    yarn = service._yarn(yarn_id)
    if not yarn:
        return {"yarn_id": yarn_id}
    return {"yarn_id": yarn_id,
            "yarn_name": " ".join(x for x in [yarn.get("brand"), yarn.get("product")] if x)}


def _gauge_fields(payload: dict) -> dict:
    def number(key):
        try:
            return float(payload[key]) if payload.get(key) is not None else None
        except (TypeError, ValueError):
            return None
    return {"hook_mm": number("hook_mm"),
            "gauge_stitches": number("gauge_stitches_per_10cm"),
            "gauge_rows": number("gauge_rows_per_10cm")}


def _user_label(user_id: int | None) -> str:
    if user_id is None:
        return "this device"
    row = user_store.get(user_id)
    return (row or {}).get("username") or f"user {user_id}"


@app.get("/api/colleagues")
def colleagues(http_request: Request):
    """Who a log can be shared with: the other active people on this server.

    Names only -- picking someone to share with should not hand out their email
    address or anything else about them.
    """
    me = _current_user_id(http_request)
    rows = [{"user_id": u["id"], "username": u["username"], "role": u["role"]}
            for u in user_store.list() if u["active"] and u["id"] != me]
    rows.sort(key=lambda r: r["username"].lower())
    return {"colleagues": rows, "me": me}


@app.get("/api/worklog")
def worklog_list(http_request: Request, owner: int | None = None, q: str | None = None,
                 kind: str | None = None, yarn_id: str | None = None,
                 limit: int = 200, offset: int = 0):
    """A log: mine by default, or a colleague's when they have shared it."""
    me = _current_user_id(http_request)
    owner_id = me if owner is None else int(owner)
    entries = worklog_store.list(owner_id=owner_id, viewer_id=me, query=q, kind=kind,
                                 yarn_id=yarn_id, limit=limit, offset=offset)
    if entries is None:
        raise HTTPException(status_code=403, detail="this log has not been shared with you")
    progress = (worklog_store.progress_for([e["entry_id"] for e in entries], me)
                if owner_id == me else {})
    for entry in entries:
        entry["progress"] = progress.get(entry["entry_id"])
    return {"owner": {"user_id": owner_id, "username": _user_label(owner_id),
                      "is_me": owner_id == me},
            "entries": entries,
            "totals": worklog_store.totals(owner_id=owner_id, viewer_id=me)}


@app.get("/api/worklog/shares")
def worklog_shares(http_request: Request):
    """Who I share my log with, and whose logs I can read."""
    me = _current_user_id(http_request)
    return {
        "me": me,
        "shared_with": [{"user_id": u, "username": _user_label(u)}
                        for u in worklog_store.viewers_of(me)],
        "shared_with_me": [{"user_id": u, "username": _user_label(u)}
                           for u in worklog_store.owners_for(me)],
    }


@app.post("/api/worklog/shares")
def worklog_share(payload: dict, http_request: Request):
    me = _current_user_id(http_request)
    if me is None:
        raise HTTPException(status_code=403, detail="sign in to share your log")
    try:
        viewer = int(payload.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="user_id is required")
    target = user_store.get(viewer)
    if target is None or not target["active"]:
        raise HTTPException(status_code=404, detail="no such person")
    if not worklog_store.share(me, viewer):
        raise HTTPException(status_code=422, detail="that is your own log")
    return {"shared_with": _user_label(viewer)}


@app.delete("/api/worklog/shares/{viewer_id}")
def worklog_unshare(viewer_id: int, http_request: Request):
    me = _current_user_id(http_request)
    worklog_store.unshare(me, viewer_id)
    return {"status": "stopped sharing", "with": _user_label(viewer_id)}


@app.get("/api/worklog/{entry_id}")
def worklog_entry(entry_id: int, http_request: Request):
    """One entry in full, including the request it can be recalculated from."""
    row = worklog_store.visible_entry(entry_id, _current_user_id(http_request))
    if row is None:
        raise HTTPException(status_code=404, detail="entry not found")
    row["request"] = json.loads(row.pop("request_json"))
    row["result"] = json.loads(row.pop("result_json"))
    row["owner_username"] = _user_label(row["user_id"])
    return row


@app.patch("/api/worklog/{entry_id}")
def worklog_update(entry_id: int, payload: dict, http_request: Request):
    row = worklog_store.update(entry_id, _current_user_id(http_request),
                               note=payload.get("note"), private=payload.get("private"),
                               title=payload.get("title"))
    if row is None:
        raise HTTPException(status_code=404, detail="entry not found")
    row.pop("request_json", None)
    row.pop("result_json", None)
    return row


@app.get("/api/worklog/{entry_id}/progress")
def worklog_progress(entry_id: int, http_request: Request):
    """How far through making this piece you are. Your own work only."""
    me = _current_user_id(http_request)
    entry = worklog_store.get(entry_id)
    if entry is None or entry["user_id"] != me:
        raise HTTPException(status_code=404, detail="entry not found")
    return worklog_store.progress(entry_id, me) or {
        "entry_id": entry_id, "current_round": 0, "done": [], "counters": [],
        "seconds": 0, "elapsed_seconds": 0, "running_since": None, "finished_at": None}


@app.put("/api/worklog/{entry_id}/progress")
def worklog_save_progress(entry_id: int, payload: dict, http_request: Request):
    row = worklog_store.save_progress(
        entry_id, _current_user_id(http_request),
        current_round=payload.get("current_round"), done=payload.get("done"),
        counters=payload.get("counters"), running=payload.get("running"),
        finished=payload.get("finished"))
    if row is None:
        raise HTTPException(status_code=404, detail="entry not found")
    return row


@app.delete("/api/worklog/{entry_id}")
def worklog_delete(entry_id: int, http_request: Request):
    if not worklog_store.delete(entry_id, _current_user_id(http_request)):
        raise HTTPException(status_code=404, detail="entry not found")
    return {"status": "deleted"}



def _log_design(http_request, design: dict, payload: dict) -> None:
    yarn = design.get("yarn") or {}
    _log_calculation(
        http_request, "design",
        f"{design.get('object') or 'Design'} — {design.get('total_height_cm')} cm, "
        f"{len(design.get('parts') or [])} parts",
        payload, design,
        **_yarn_fields(payload.get("yarn_id")),
        **_colour_fields(design.get("colour")),
        **_gauge_fields(payload),
        length_m=yarn.get("length_m"), mass_g=yarn.get("mass_g"),
        packages=yarn.get("packages"), stitches=design.get("total_stitches"),
        pieces=design.get("piece_count"))


# ------------------------------------------------------- importing a pattern --
IMPORT_MAX_BYTES = 4 * 1024 * 1024


def _import_result(text: str, dialect: str, source: str) -> dict:
    """Read a written pattern into rounds, and say plainly what it could not read."""
    parsed = parse_crochet_rounds(text or "", dialect=("uk" if dialect == "uk" else "us"))
    out = parsed.as_dict()
    out["source"] = source
    out["text"] = text[:20000]
    if out["rounds"]:
        analysed = analyse_rounds({"initial_stitches": out["initial_stitches"] or 6,
                                   "rounds": out["rounds"]}, service.operations)
        out["valid"] = bool(analysed.get("valid"))
        out["program_issues"] = analysed.get("issues", [])
        # written out with the same writer the rest of the app uses, so what is
        # previewed here is what the make-mode will read out
        out["written"] = ([f"R1: {out['initial_stitches']} sc in magic ring "
                           f"({out['initial_stitches']})"] +
                          [f"R{i}: " + round_text(r["operations"], t["output_stitches"])
                           for i, (r, t) in enumerate(zip(out["rounds"],
                                                          analysed.get("trace") or []), start=2)]
                          ) if analysed.get("valid") else []
    else:
        out["valid"] = False
        out["program_issues"] = []
        out["written"] = []
    return out


@app.post("/api/crochet/round/read")
def read_one_round(payload: dict):
    """One round, typed the way a pattern writes it.

    Someone who has crocheted for thirty years reads and writes a round as a
    line of text — "[2 sc, inc] x 6" — and assembling that out of dropdowns is
    slower than a pencil. This reads the line with the same parser the pattern
    import uses, so anything a pattern can say, the editor can take.
    """
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="type the round first")
    incoming = payload.get("incoming")
    incoming = int(incoming) if incoming not in (None, "") else None
    dialect = "uk" if str(payload.get("dialect") or "us") == "uk" else "us"
    vocab = crochet_vocabulary(dialect)
    # A round number at the front is how it is written; it is not part of the
    # stitches, so it is taken off before reading.
    body = ROUND_HEADER.sub("", text) if ROUND_HEADER.match(text) else text
    header = ROUND_HEADER.match(text)
    if header:
        body = header.group(3)
    ops, why = parse_one_round(body, vocab, incoming)
    if ops is None:
        # the parser already says what defeated it; do not say it twice
        reason = str(why or "").strip()
        # The parser names the fragment that defeated it; quote that rather than
        # repeating its sentence inside another one.
        for opener in ("a repeat could not be read:", "could not read:"):
            if reason.lower().startswith(opener):
                reason = f"“{reason[len(opener):].strip()}” is not something it can read"
                break
        raise HTTPException(status_code=422, detail=(
            f"That round could not be read — {reason}. "
            "Write it the way a pattern does: “[2 sc, inc] x 6”, “sc in each st around”, "
            "“6 inc”."))
    produced = sum(service.operations[op]["produces_stitches"] * n
                   for op, n in ops.items() if op in service.operations)
    consumed = sum(service.operations[op]["consumes_stitches"] * n
                   for op, n in ops.items() if op in service.operations)
    if incoming is not None and consumed != incoming:
        issue = {"code": "ROUND_INPUT_MISMATCH", "expected": incoming, "consumed": consumed}
        if payload.get("round"):
            issue["round"] = int(payload["round"])
        raise HTTPException(status_code=422, detail=plain_problem(
            [issue], str(payload.get("row_word") or "round")))
    return {"operations": ops, "output_stitches": produced, "consumed": consumed,
            "written": round_text(ops, produced, words=crochet_terms.words(dialect)),
            "terms": dialect}


@app.post("/api/import/rounds")
def import_rounds(payload: dict):
    """Pasted or typed pattern text -> rounds."""
    text = str(payload.get("text") or "")
    if not text.strip():
        raise HTTPException(status_code=422, detail="paste the pattern text first")
    if len(text) > 200_000:
        raise HTTPException(status_code=422, detail="that is a very large pattern; import one part at a time")
    return _import_result(text, str(payload.get("dialect") or "us"), "text")


@app.post("/api/import/file")
def import_file(payload: dict):
    """A pattern file: plain text, markdown, or a PDF whose text can be read.

    A PDF of a scan is images, not text; when nothing comes out, the answer says
    so and points at the photo route rather than returning an empty pattern.
    """
    name = str(payload.get("filename") or "pattern")
    try:
        blob = base64.b64decode(str(payload.get("data") or ""), validate=True)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="the file could not be read")
    if len(blob) > IMPORT_MAX_BYTES:
        raise HTTPException(status_code=422, detail="the file is too large (maximum 4 MB)")
    if name.lower().endswith(".pdf") or blob[:5] == b"%PDF-":
        try:
            import pdfplumber, io as _io
            with pdfplumber.open(_io.BytesIO(blob)) as pdf:
                text = "\n".join((page.extract_text() or "") for page in pdf.pages[:40])
        except Exception as e:                       # noqa: BLE001 - any broken PDF
            raise HTTPException(status_code=422, detail=f"the PDF could not be read: {e}")
        if not text.strip():
            raise HTTPException(status_code=422, detail=(
                "this PDF holds pictures of the pages rather than text, so there is "
                "nothing to read out of it — photograph or screenshot the pattern and "
                "use “From a photo” instead"))
    else:
        try:
            text = blob.decode("utf-8")
        except UnicodeDecodeError:
            text = blob.decode("latin-1", "replace")
    return _import_result(text, str(payload.get("dialect") or "us"), name)


@app.post("/api/import/photo")
def import_photo(payload: dict, http_request: Request):
    """A photographed or scanned pattern: transcribed, then read as rounds.

    The model only transcribes; what the stitches mean is worked out afterwards
    by the same deterministic reader the pasted text goes through, so a
    misreading shows up as an unreadable line rather than as invented rounds.
    """
    _check_photo_rate_limit(http_request)
    images = []
    for item in (payload.get("images") or [])[:4]:
        try:
            media = str(item.get("media_type") or "image/jpeg")
            data = str(item.get("data") or "")
            if "," in data and data.strip().startswith("data:"):
                media = data.split(";")[0][5:] or media
                data = data.split(",", 1)[1]
            images.append((media, base64.b64decode(data, validate=True)))
        except (AttributeError, ValueError, TypeError):
            raise HTTPException(status_code=422, detail="an image could not be read")
    if not images:
        raise HTTPException(status_code=422, detail="at least one photo is required")
    key, model = _vision_settings()
    try:
        text = transcribe_pattern(images, api_key=key, model=model)
    except VisionUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    out = _import_result(text, str(payload.get("dialect") or "us"), "photo")
    out["notes"] = list(out.get("notes") or []) + [
        "Read from a photo, so check the stitch counts against the page before making it."]
    return out


@app.get("/api/import/sources")
def import_sources():
    """Where a pattern can come from, and where it honestly cannot."""
    key, _ = _vision_settings()
    return {"sources": [
        {"id": "text", "name": "Paste the text", "available": True,
         "note": "Works with anything you can copy: an email, a page, a message."},
        {"id": "file", "name": "A file", "available": True,
         "note": "Plain text, markdown, or a PDF that holds real text."},
        {"id": "photo", "name": "From a photo", "available": vision_configured(key),
         "note": ("A photograph or screenshot of a printed pattern, transcribed and then read."
                  if vision_configured(key) else
                  "Needs the vision key on the admin page.")},
        {"id": "link", "name": "A web address", "available": False,
         "note": ("Not offered: fetching someone's pattern page and keeping it here is "
                  "their copyright, not ours. Open the page and paste the rounds instead.")},
        {"id": "ravelry", "name": "Ravelry", "available": False,
         "note": ("Not offered: a Ravelry pattern is licensed to you, not to this app, "
                  "and there is no route that legitimately hands it over. Download your "
                  "copy and import the file or paste the text.")},
        {"id": "youtube", "name": "YouTube", "available": False,
         "note": ("Not offered: a video has no pattern text to read. Written notes from "
                  "the description can be pasted in.")},
    ]}


@app.post("/api/design/generate")
def design_generate(payload: dict, http_request: Request):
    """Parts + a stated height -> the pattern for every part.

    Deterministic and offline: no photo, no API key. This is the step that
    produces every number a maker works from.
    """
    try:
        design = build_design(payload)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    _cost_design_in_yarn(design, payload)
    _assign_colours(design, payload)
    design["written"] = written_pattern(design)
    _log_design(http_request, design, payload)
    return design


PHOTO_MAX_PER_HOUR = 20
_photo_calls: dict[str, list[float]] = defaultdict(list)

def _check_photo_rate_limit(request: Request):
    """Each photo read costs real money at the vision provider, so cap how many
    one account can trigger per hour."""
    user = getattr(request.state, "user", None)
    key = str(user["id"]) if user else "anonymous"
    now = time.monotonic()
    calls = _photo_calls[key]
    while calls and calls[0] < now - 3600:
        calls.pop(0)
    if len(calls) >= PHOTO_MAX_PER_HOUR:
        raise HTTPException(status_code=429, detail=(
            f"photo analysis is limited to {PHOTO_MAX_PER_HOUR} photos an hour; "
            "describe the parts yourself in the meantime"))
    calls.append(now)


@app.post("/api/design/from-photo")
def design_from_photo(payload: dict, http_request: Request):
    """Photo(s) + an approximate height -> the parts, then their patterns.

    The vision model only describes the parts and their proportions; every
    stitch count and round count below comes from the deterministic generator.
    """
    _check_photo_rate_limit(http_request)
    images = []
    for item in (payload.get("images") or [])[:4]:
        try:
            media = str(item.get("media_type") or "image/jpeg")
            data = str(item.get("data") or "")
            if "," in data and data.strip().startswith("data:"):
                media = data.split(";")[0][5:] or media
                data = data.split(",", 1)[1]
            images.append((media, base64.b64decode(data, validate=True)))
        except (AttributeError, ValueError, TypeError):
            raise HTTPException(status_code=422, detail="an image could not be read")
    if not images:
        raise HTTPException(status_code=422, detail="at least one photo is required")
    stored_key, stored_model = _vision_settings()
    try:
        described = describe_photo(images, hint=payload.get("hint"),
                                   api_key=stored_key, model=stored_model)
    except VisionUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
    spec = {
        "object": described["object"],
        "total_height_cm": payload.get("total_height_cm"),
        "gauge_stitches_per_10cm": payload.get("gauge_stitches_per_10cm", 20),
        "gauge_rows_per_10cm": payload.get("gauge_rows_per_10cm", 22),
        "initial_stitches": payload.get("initial_stitches", 6),
        "parts": described["parts"],
        "notes": described["assembly"],
    }
    try:
        design = build_design(spec)
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    _cost_design_in_yarn(design, payload)
    _assign_colours(design, payload, described)
    design["written"] = written_pattern(design)
    design["photo_reading"] = {
        "confidence": described["confidence"],
        "uncertain": described["uncertain"],
        "dropped": described["dropped"],
        "model": described.get("model"),
    }
    _log_design(http_request, design, payload)
    return design


@app.api_route("/", methods=["GET", "HEAD"])
def index():
    # HEAD is used by the in-page version check (ETag comparison) so an open
    # tab can offer "Update now" when a newer deploy is live.
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
def complex_consumption_calculate(payload:dict, http_request:Request):
    kind=payload.get("program_type")
    program=payload.get("program",{})
    # How the piece is built. The engine below is the same whatever the answer;
    # what changes is how the piece starts and what its stitch counts mean.
    try:
        construction=constructions.get(payload.get("construction") or kind)
    except KeyError:
        raise HTTPException(status_code=422, detail=(
            f"construction must be one of {sorted(constructions.CONSTRUCTIONS)}"))
    if construction.id=="branched":
        analysed=execute_branch_program(program,service.operations)
    else:
        analysed=analyse_rounds(program,service.operations)
        trace=analysed.get("trace") or []
        issue=constructions.start_issue(
            construction.id, int(program.get("initial_stitches") or 0),
            int(trace[0].get("consumed") or 0) if trace else 0)
        if issue is not None:
            analysed={**analysed,"valid":False,
                      "issues":list(analysed.get("issues") or [])+[issue]}
    if not analysed.get("valid"):
        raise HTTPException(status_code=422,
                            detail=plain_problem(analysed.get("issues", []), construction.row_word))
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
    result={"program_type":kind,"program_analysis":analysed,"calculation":calc.__dict__,
            "prediction":{"estimate_m":pred.estimate_m,"lower_95_m":pred.lower_95_m,"upper_95_m":pred.upper_95_m,"in_domain":pred.in_domain,"warnings":pred.warnings},
            "audit":{**audit,"yarn_diameter_mm":diameter,"yarn_diameter_source":diameter_source,"yarn_diameter_warnings":list(diameter_warnings)},
            "model_id":production["model_id"] if production else UNCALIBRATED_BASELINE_MODEL_ID}
    copies=max(1,int(payload.get("copies") or 1))
    stitches=sum(int(v) for v in analysed["operation_counts"].values())
    rounds=len(analysed.get("trace") or [])
    # What the log calls this piece. Older entries were all "amigurumi" because
    # that was the only thing the app made; a piece now records how it was
    # built, which is the thing worth knowing when it comes back.
    logged=_log_calculation(
        http_request, kind or construction.id,
        payload.get("title") or (f"{construction.name} — {rounds} {construction.row_word}s"),
        payload, result,
        **_yarn_fields(payload.get("yarn_id")),
        **_colour_fields(_public_colour(_colour(payload.get("colour_id")))),
        **_gauge_fields(payload),
        length_m=(calc.recommended_length_m*copies if calc.recommended_length_m is not None else None),
        mass_g=(calc.mass_g*copies if calc.mass_g is not None else None),
        packages=calc.packages, stitches=stitches*copies, pieces=copies)
    # so the result can offer to work through the piece straight away
    result["worklog_entry_id"] = (logged or {}).get("entry_id")
    result["construction"]=construction.as_dict()
    try:
        result["finished_size"]=constructions.finished_size(
            construction.id, analysed.get("trace") or [],
            gauge_stitches_per_10cm=float(payload.get("gauge_stitches_per_10cm") or 0),
            gauge_rows_per_10cm=float(payload.get("gauge_rows_per_10cm") or 0),
            initial_stitches=int((program or {}).get("initial_stitches") or 0),
            layout=payload.get("layout"))
    except (ValueError, KeyError):
        result["finished_size"]=None
    return result

@app.get("/api/beginner/projects")
def beginner_projects():
    """What a first piece can be, in the words someone would use for it."""
    return {"projects": [{"id": key, **{k: v for k, v in spec.items() if k != "firm"}}
                         for key, spec in beginner.PROJECTS.items()]}


@app.post("/api/beginner/plan")
def beginner_plan(payload: dict, http_request: Request):
    """Two answers — what, and how big — turned into a real piece.

    Everything the calculator would have asked for is worked out from the yarn
    and said out loud: which hook, which gauge, and that a swatch beats both.
    """
    project_id = str(payload.get("project") or "")
    if project_id not in beginner.PROJECTS:
        raise HTTPException(status_code=422,
                            detail=f"choose one of: {', '.join(beginner.PROJECTS)}")
    spec = beginner.PROJECTS[project_id]
    yarn = service._yarn(payload.get("yarn_id")) if payload.get("yarn_id") else None
    if yarn is None:
        raise HTTPException(status_code=422, detail="choose a yarn first")

    gauge = beginner.suggest_gauge(yarn.get("cyc_weight"), firm=spec["firm"])
    # Anything the person has actually measured beats what was suggested.
    for key in ("gauge_stitches_per_10cm", "gauge_rows_per_10cm", "hook_mm"):
        if payload.get(key) not in (None, ""):
            gauge = {**gauge, key: float(payload[key]), "known": True,
                     "note": "Using the gauge you measured."}
    try:
        built = beginner.build(project_id, payload.get("answers") or {}, gauge)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    body = {"construction": built["construction"], "program": built["program"],
            "yarn_id": payload.get("yarn_id"), "hook_mm": gauge["hook_mm"],
            "gauge_stitches_per_10cm": gauge["gauge_stitches_per_10cm"],
            "gauge_rows_per_10cm": gauge["gauge_rows_per_10cm"],
            "allowance_percent": float(payload.get("allowance_percent") or 10),
            "domain_policy": "warn", "colour_id": payload.get("colour_id"),
            "copies": int(payload.get("copies") or 1),
            "title": payload.get("title") or spec["name"]}
    costed = complex_consumption_calculate(body, http_request)
    written = crochet_amigurumi_written({**built["program"],
                                         "construction": built["construction"],
                                         "terms": payload.get("terms")})
    # Everything worth knowing in one list, in the order it matters: where the
    # hook and gauge came from first, because that is what the size rests on.
    notes = [gauge["note"]] + built["notes"] + list(written.get("notes") or [])
    return {"project": project_id, "name": spec["name"], "about": spec["about"],
            "gauge": gauge, "notes": notes,
            "written": written["lines"], "terms": written.get("terms"),
            "result": costed, "body": body}


@app.get("/api/constructions")
def list_constructions(craft: str | None = None):
    """Every way of building a piece the app knows, and what each one means.

    A stitch count is a circumference on one of these and a width on another;
    "round 1" is a magic ring here and a cast-on there. Asking rather than
    assuming is what lets the same engine cost a jumper and a bear.
    """
    if craft not in (None, "crochet", "knitting"):
        raise HTTPException(status_code=422, detail="craft must be crochet or knitting")
    return {"constructions": constructions.listing(craft), "default": constructions.DEFAULT}


@app.post("/api/crochet/amigurumi/written")
def crochet_amigurumi_written(payload: dict):
    """Rounds -> the lines a person actually reads while making it.

    The same writer the generated patterns use, so a piece reads identically
    whether it came out of the designer or was typed into the rounds editor.
    """
    analysed = analyse_rounds(payload, service.operations)
    if not analysed.get("valid"):
        raise HTTPException(status_code=422,
                            detail=plain_problem(analysed.get("issues", [])))
    # Which stitch the piece is mostly worked in decides how the rounds read
    # and what goes into the ring. A piece of trebles that starts "12 sc in
    # magic ring" is wrong in a way every crocheter would catch.
    def _mainstay() -> str:
        tally: dict[str, int] = {}
        for r in payload.get("rounds", []):
            for op, n in (r.get("operations") or {}).items():
                base = {"SC_INC": "SC", "SC2TOG": "SC", "SC3TOG": "SC",
                        "HDC_INC": "HDC", "HDC2TOG": "HDC",
                        "DC_INC": "DC", "DC2TOG": "DC", "DC3TOG": "DC"}.get(op, op)
                if base in ("SC", "HDC", "DC", "TR", "DTR"):
                    tally[base] = tally.get(base, 0) + int(n or 0)
        return max(tally, key=tally.get) if tally else "SC"

    stitch = str(payload.get("stitch") or _mainstay()).upper()
    initial = int(payload.get("initial_stitches") or 6)
    dialect = crochet_terms.normalise(payload.get("terms"))
    # The same stitches, printed in the words the maker reads in.
    terms = crochet_terms.words(dialect)
    word = terms.get(stitch, "sc")
    try:
        construction = constructions.get(payload.get("construction"))
    except KeyError:
        raise HTTPException(status_code=422, detail=(
            f"construction must be one of {sorted(constructions.CONSTRUCTIONS)}"))
    # A pattern says how the piece begins, and that is not the same sentence for
    # a stuffed head, a sleeve and a blanket.
    prefix = "R" if construction.row_word == "round" else "Row "
    if construction.closed_start:
        first = f"{initial} {word} in magic ring"
    elif construction.start == "ring_of_stitches":
        first = f"ch {initial}, join into a ring, {word} in each ch"
    else:
        first = f"ch {initial + 1}, {word} in 2nd ch from hook and in each ch across"
    lines = [f"{prefix}1: {first} ({initial})"]
    for i, (r, step) in enumerate(zip(payload.get("rounds", []), analysed["trace"]), start=2):
        lines.append(f"{prefix}{i}: " + round_text(
            r.get("operations", {}), step["output_stitches"], plain=stitch,
            closing=("around" if construction.row_word == "round" else "across"),
            words=terms))
    return {"lines": lines, "stitch_counts": [initial] + [t["output_stitches"] for t in analysed["trace"]],
            "round_count": len(lines), "construction": construction.as_dict(),
            "terms": dialect,
            "notes": ([("Turning chains are not in these counts. Most flat patterns work one at "
                        "the start of each row — add them if yours does, and the yarn figure "
                        "will go up a little.")]
                      if construction.row_word == "row" else [])}


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


# ------------------------------------------------------------------ tools ----
def _bad(exc: Exception):
    return HTTPException(status_code=422, detail=str(exc))


@app.post("/api/tools/spread")
def tools_spread(payload: dict):
    """Increases or decreases spaced evenly round a piece."""
    try:
        if payload.get("target") not in (None, ""):
            return tool_maths.change_to_target(
                int(payload["stitches"]), int(payload["target"]),
                str(payload.get("stitch") or "SC").upper())
        return tool_maths.spread_evenly(
            int(payload["stitches"]), int(payload.get("change") or 0),
            str(payload.get("stitch") or "SC").upper())
    except (ValueError, TypeError, KeyError) as e:
        raise _bad(e)


@app.post("/api/tools/size")
def tools_size(payload: dict):
    """Stitches and rows to centimetres, or centimetres to stitches and rows."""
    def maybe(key):
        value = payload.get(key)
        return None if value in (None, "") else float(value)
    try:
        return tool_maths.size_from_gauge(
            float(payload.get("gauge_stitches_per_10cm") or 0),
            float(payload.get("gauge_rows_per_10cm") or 0),
            stitches=(int(payload["stitches"]) if payload.get("stitches") else None),
            rows=(int(payload["rows"]) if payload.get("rows") else None),
            width_cm=maybe("width_cm"), height_cm=maybe("height_cm"))
    except (ValueError, TypeError) as e:
        raise _bad(e)


@app.get("/api/tools/sizes")
def tools_sizes(kind: str = "hook"):
    """The whole published conversion chart, with where it comes from."""
    if kind not in ("hook", "needle"):
        raise HTTPException(status_code=422, detail="kind must be hook or needle")
    tables = tool_maths.size_tables(ROOT)
    return {"kind": kind, "sources": tables["sources"],
            "sizes": tables["crochet_hooks" if kind == "hook" else "knitting_needles"]}


@app.get("/api/tools/size-convert")
def tools_size_convert(kind: str = "hook", mm: float | None = None,
                       us: str | None = None, uk: str | None = None):
    try:
        return tool_maths.convert_size(ROOT, kind, mm=mm, us=us, uk=uk)
    except (ValueError, TypeError) as e:
        raise _bad(e)


@app.post("/api/tools/units")
def tools_units(payload: dict):
    """Plain units, and -- for one stated ball -- length against weight."""
    try:
        if payload.get("yarn_id"):
            yarn = service._yarn(payload["yarn_id"])
            if yarn is None:
                raise HTTPException(status_code=404, detail="no such yarn")
            out = tool_maths.yarn_amount(
                float(yarn["package_mass_g"]), float(yarn["package_length_m"]),
                length_m=(float(payload["length_m"]) if payload.get("length_m") else None),
                mass_g=(float(payload["mass_g"]) if payload.get("mass_g") else None))
            out["yarn"] = f"{yarn['brand']} {yarn['product']}"
            out["package"] = f"{yarn['package_mass_g']} g / {yarn['package_length_m']} m"
            return out
        return tool_maths.convert_units(float(payload["value"]), str(payload["unit"]))
    except (ValueError, TypeError, KeyError) as e:
        raise _bad(e)


@app.post("/api/tools/squares")
def tools_squares(payload: dict):
    """A blanket of granny squares: the layout, and what it really measures."""
    try:
        return tool_maths.plan_squares(
            float(payload.get("width_cm") or 0), float(payload.get("height_cm") or 0),
            float(payload.get("square_cm") or 0),
            join_cm=float(payload.get("join_cm") or 0),
            border_cm=float(payload.get("border_cm") or 0),
            gauge_rows_per_10cm=(float(payload["gauge_rows_per_10cm"])
                                 if payload.get("gauge_rows_per_10cm") else None))
    except (ValueError, TypeError) as e:
        raise _bad(e)


@app.post("/api/tools/price")
def tools_price(payload: dict, http_request: Request):
    """What a piece costs to make, and what it might sell for.

    The yarn and the hours are taken from the work log where they exist, so the
    price is built on what the piece actually took rather than on a guess.
    """
    length_m = payload.get("length_m")
    pieces = int(payload.get("pieces") or 1)
    hours = payload.get("hours")
    yarn_id = payload.get("yarn_id")
    source = "typed in"
    if payload.get("entry_id"):
        me = _current_user_id(http_request)
        entry = worklog_store.get(int(payload["entry_id"]))
        if entry is None or entry["user_id"] != me:
            raise HTTPException(status_code=404, detail="entry not found")
        length_m = entry.get("length_m")
        pieces = int(entry.get("pieces") or 1)
        yarn_id = entry.get("yarn_id") or yarn_id
        progress = worklog_store.progress(int(payload["entry_id"]), me)
        if hours in (None, "") and progress:
            hours = progress["elapsed_seconds"] / 3600
        source = entry.get("title") or "work log entry"
    if length_m in (None, ""):
        raise HTTPException(status_code=422, detail="calculate the piece first, or type in how much yarn it takes")
    yarn = service._yarn(yarn_id) if yarn_id else None
    price_per_package = payload.get("price_per_package")
    if price_per_package in (None, ""):
        price_per_package = (yarn or {}).get("price_amount")
    currency = (payload.get("currency") or (yarn or {}).get("price_currency") or "GBP")
    try:
        out = price_piece(
            length_m=float(length_m),
            package_length_m=((yarn or {}).get("package_length_m")
                              or (float(payload["package_length_m"])
                                  if payload.get("package_length_m") else None)),
            price_per_package=(float(price_per_package) if price_per_package not in (None, "") else None),
            currency=str(currency)[:3].upper(),
            hours=float(hours or 0), hourly_rate=float(payload.get("hourly_rate") or 0),
            extras=payload.get("extras") or [],
            overhead_percent=float(payload.get("overhead_percent") or 0),
            margin_percent=float(payload.get("margin_percent") or 0),
            vat_percent=float(payload.get("vat_percent") or 0),
            whole_packages=bool(payload.get("whole_packages")),
            pieces=pieces)
    except (ValueError, TypeError) as e:
        raise _bad(e)
    out["from"] = source
    out["yarn"] = f"{yarn['brand']} {yarn['product']}" if yarn else None
    out["time_from_log"] = bool(payload.get("entry_id") and payload.get("hours") in (None, ""))
    return out


@app.get("/api/tools/gauges")
def list_gauges(http_request: Request):
    """Swatches already measured, ready to use again."""
    store = service._store()
    try:
        return {"gauges": store.list_gauges(_current_user_id(http_request))}
    finally:
        store.close()


@app.post("/api/tools/gauges")
def save_gauge(payload: dict, http_request: Request):
    name = str(payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="give the swatch a name")
    def positive(key):
        try:
            value = float(payload.get(key))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{key} must be a number")
        if not 0 < value <= 200:
            raise HTTPException(status_code=422, detail=f"{key} is outside anything a swatch measures")
        return value
    swatch = {"id": payload.get("id"), "name": name[:80],
              "yarn_id": payload.get("yarn_id") or None,
              "hook_mm": (float(payload["hook_mm"]) if payload.get("hook_mm") else None),
              "stitch": (str(payload.get("stitch") or "SC").upper()[:12]),
              "stitches_per_10cm": positive("stitches_per_10cm"),
              "rows_per_10cm": positive("rows_per_10cm"),
              "notes": (str(payload.get("notes") or "").strip()[:300] or None)}
    store = service._store()
    try:
        store.save_gauge(_current_user_id(http_request), swatch,
                         datetime.datetime.now(datetime.timezone.utc).isoformat())
        return {"status": "saved", "gauge": swatch}
    finally:
        store.close()


@app.delete("/api/tools/gauges/{gauge_id}")
def delete_gauge(gauge_id: int, http_request: Request):
    store = service._store()
    try:
        if not store.delete_gauge(_current_user_id(http_request), gauge_id):
            raise HTTPException(status_code=404, detail="not one of your swatches")
    finally:
        store.close()
    return {"status": "deleted"}


# ------------------------------------------------------------- the stitches ---
# What each stitch is for, in the words a person would use. Everything else on
# this page -- how much yarn it takes, what it consumes and produces -- is read
# from the operation registry and the geometry, not written down twice.
STITCH_USES = {
    "CH": "Starts a row and makes the gaps in lacy fabric. Adds a stitch without using one.",
    "SLST": "Joins, travels and finishes. Adds no height at all.",
    "SC": "The amigurumi stitch: short and dense, so stuffing does not show through.",
    "SC_BLO": "Single crochet through the back loop only, which leaves a ridge — used for a fold or a sole.",
    "SC_FLO": "Single crochet through the front loop only; the ridge faces the other way.",
    "HDC": "Half again as tall as single crochet. Quicker, still fairly dense.",
    "DC": "Twice the height of single crochet. Blankets and garments, where drape matters more than density.",
    "TR": "Taller again, and openly holey. Lace and edgings.",
    "DTR": "The tallest of the everyday stitches.",
    "SC_INC": "Two single crochet in one stitch: this is how a flat circle grows.",
    "HDC_INC": "The same increase worked in half double crochet.",
    "DC_INC": "The same increase worked in double crochet.",
    "SC2TOG": "Two stitches worked together as one: how a ball closes up.",
    "SC3TOG": "Three into one, for a sharper decrease.",
    "HDC2TOG": "The half double crochet decrease.",
    "DC2TOG": "The double crochet decrease.",
    "FPDC": "Worked around the post from the front, raising a ridge towards you — ribbing and cables.",
    "BPDC": "The same from the back, so the ridge falls away.",
    "PUFF3": "Several loops drawn up and closed together into a soft bump.",
    "POPCORN5": "A cluster folded forward into a firm bobble.",
}
# The order a person meets them, not the order a computer sorts them: a chart
# that opens on "back post double crochet" is a chart nobody reads.
STITCH_ORDER = ["CH", "SLST", "SC", "HDC", "DC", "TR", "DTR",
                "SC_INC", "HDC_INC", "DC_INC",
                "SC2TOG", "SC3TOG", "HDC2TOG", "DC2TOG", "DC3TOG",
                "SC_BLO", "SC_FLO", "HDC_BLO", "DC_BLO",
                "FPDC", "BPDC", "PUFF3", "POPCORN5"]


@app.get("/api/terms")
def crochet_term_table():
    """Both names for every stitch, and the ones that are the same either side.

    A pattern that does not say whether it is written in UK or US terms can
    quietly ruin a piece: "dc" is single crochet in Britain and a stitch twice
    as tall in America.
    """
    return {"dialects": list(crochet_terms.DIALECTS), "default": crochet_terms.DEFAULT,
            "headline": crochet_terms.HEADLINE, "stitches": crochet_terms.table(),
            "shared": crochet_terms.SHARED}


@app.get("/api/stitches")
def stitches(hook_mm: float = 3.5, yarn_diameter_mm: float = 2.5, terms: str = "us"):
    """Every crochet stitch the app knows, and what each one costs.

    The yarn figure is the geometry baseline at a stated hook and yarn, so it
    is comparable between stitches rather than being a number to work from: a
    double crochet takes about twice what a single crochet does, which is the
    thing worth knowing when choosing one.
    """
    if not 0 < hook_mm <= 30 or not 0 < yarn_diameter_mm <= 15:
        raise HTTPException(status_code=422, detail="hook and yarn diameter are in millimetres")
    out = []
    def teaching_order(pair):
        op_id = pair[0]
        return (STITCH_ORDER.index(op_id) if op_id in STITCH_ORDER else len(STITCH_ORDER), op_id)
    for op_id, op in sorted(operation_map.items(), key=teaching_order):
        family = (op.get("family") or "")
        if not family.startswith("crochet"):
            continue
        try:
            length = operation_length_mm(op_id, hook_mm, yarn_diameter_mm)
            per_stitch_mm, measured = length.length_mm, length.measured_anchor
        except KeyError:
            per_stitch_mm, measured = None, False
        out.append({
            "operation_id": op_id,
            "name": crochet_terms.name(op_id, terms) or op.get("name") or op_id,
            "abbreviation": crochet_terms.abbr(op_id, terms),
            "other_name": (crochet_terms.name(op_id, "uk" if crochet_terms.normalise(terms) == "us" else "us")
                           if crochet_terms.differs(op_id) else None),
            "other_abbr": (crochet_terms.abbr(op_id, "uk" if crochet_terms.normalise(terms) == "us" else "us")
                           if crochet_terms.differs(op_id) else None),
            "family": family,
            "consumes": op.get("consumes_stitches"),
            "produces": op.get("produces_stitches"),
            "wraps": OPERATION_WRAPS.get(op_id),
            "yarn_mm": round(per_stitch_mm, 1) if per_stitch_mm else None,
            "relative_to_sc": (round(OPERATION_WRAP_RATIO[op_id], 2)
                               if op_id in OPERATION_WRAP_RATIO else None),
            "measured": measured,
            "use": STITCH_USES.get(op_id),
        })
    return {"hook_mm": hook_mm, "yarn_diameter_mm": yarn_diameter_mm,
            "terms": crochet_terms.normalise(terms), "stitches": out,
            "note": ("Yarn per stitch is the uncalibrated geometry baseline at this hook and "
                     "yarn: wraps x tension x the loop around hook and yarn. It is for "
                     "comparing stitches, not for costing a piece — the calculator does that "
                     "from the whole program.")}


# ------------------------------------------------------ the rest of the kit ---
STASH_KINDS = {
    "hook": "Hooks", "needle": "Needles", "supply": "Supplies", "tool": "Tools",
}


@app.get("/api/stash/items")
def list_stash_items(http_request: Request, kind: str | None = None, q: str | None = None):
    """Hooks, needles and the oddments, which is most of what a bag holds."""
    if kind and kind not in STASH_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(STASH_KINDS)}")
    store = service._store()
    try:
        items = store.list_stash_items(_current_user_id(http_request), kind=kind, query=q)
        all_items = store.list_stash_items(_current_user_id(http_request))
    finally:
        store.close()
    counts = {k: 0 for k in STASH_KINDS}
    for item in all_items:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    return {"items": items, "kinds": STASH_KINDS, "counts": counts}


@app.post("/api/stash/items")
def upsert_stash_item(payload: dict, http_request: Request):
    kind = str(payload.get("kind") or "").strip()
    name = str(payload.get("name") or "").strip()
    if kind not in STASH_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {sorted(STASH_KINDS)}")
    if not name:
        raise HTTPException(status_code=422, detail="give it a name")
    def number(key, default=None):
        value = payload.get(key)
        if value in (None, ""):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{key} must be a number")
    size = number("size_mm")
    if size is not None and not 0 < size <= 50:
        raise HTTPException(status_code=422, detail="a hook or needle is between 0 and 50 mm")
    quantity = number("quantity", 1.0)
    if quantity is None or quantity < 0:
        raise HTTPException(status_code=422, detail="how many is not a negative number")
    item = {"id": payload.get("id"), "kind": kind, "name": name[:120],
            "brand": (str(payload.get("brand") or "").strip()[:80] or None),
            "size_mm": size, "size_label": (str(payload.get("size_label") or "").strip()[:20] or None),
            "quantity": quantity, "notes": (str(payload.get("notes") or "").strip()[:300] or None)}
    store = service._store()
    try:
        store.upsert_stash_item(_current_user_id(http_request), item,
                                datetime.datetime.now(datetime.timezone.utc).isoformat())
        return {"status": "saved", "item": item}
    finally:
        store.close()


@app.delete("/api/stash/items/{item_id}")
def delete_stash_item(item_id: int, http_request: Request):
    store = service._store()
    try:
        if not store.delete_stash_item(_current_user_id(http_request), item_id):
            raise HTTPException(status_code=404, detail="not in your stash")
    finally:
        store.close()
    return {"status": "deleted"}


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
        result = service.calculate(request, user_id=_current_user_id(http_request))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    payload = request.model_dump() if hasattr(request, "model_dump") else request.dict()
    consumption = result.get("consumption") or {}
    project = result.get("project") or {}
    pattern = result.get("pattern") or {}
    _log_calculation(
        http_request, "flat",
        f"{pattern.get('name') or 'Flat piece'} — {payload.get('width_cm')}×{payload.get('height_cm')} cm",
        payload, result,
        **_yarn_fields(payload.get("yarn_id")),
        **_colour_fields(_public_colour(_colour(payload.get("colour_id")))),
        **_gauge_fields(payload),
        length_m=consumption.get("recommended_length_m"), mass_g=consumption.get("mass_g"),
        packages=consumption.get("packages"),
        stitches=(project.get("stitches") or 0) * (project.get("rows") or 0) or None,
        pieces=1)
    return result
