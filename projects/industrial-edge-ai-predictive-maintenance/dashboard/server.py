"""EDGEOPS dashboard development backend.

Local-first prototype, not industrial production approval. Same-origin secure
session design, SQLite audit trail, read-only synthetic catalog, no actuation.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal

from request_limits import RequestBodyLimit, SECURITY_HEADERS
import physical_build
import incidents
import observation_queries
import delivery_service
import acquisition_registry
import operations
import telemetry_store
import maintenance_requests
import maintenance_exercises
import team_accounts
import production_readiness
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("EDGEOPS_DASHBOARD_DB", str(ROOT / ".local" / "dashboard.sqlite3"))).resolve()
SESSION_HOURS = 8
SESSION_SECONDS = SESSION_HOURS * 3600
COOKIE = "edgeops_session"
CSRF_COOKIE = "edgeops_csrf"
HTTPS_ONLY = os.environ.get("EDGEOPS_HTTPS_ONLY", "0") == "1"
BOOTSTRAP_EMAIL = os.environ.get("EDGEOPS_ADMIN_EMAIL", "").strip().lower()
BOOTSTRAP_PASSWORD = os.environ.get("EDGEOPS_ADMIN_PASSWORD", "")
MAX_BODY_BYTES = 8192

app = FastAPI(title="EDGEOPS Industrial Console", docs_url=None, redoc_url=None, openapi_url=None)
PUBLIC_ASSETS = {"persisted-observation-comparison.js", "persisted-observation-inspector.js", "planning-revision-comparison.js", "planning-workbench-ui.js", "planning-draft-guard.js", "planning-source-context.js", "incident-saved-check.js", "incident-handover-ui.js", "incident-draft-guard.js", "incident-capture-comparison.js", "incident-workbench-ui.js", "incident-triage-ui.js", "incident-observations-ui.js", "styles.css", "app.js", "dashboard-auth.js", "comparison-ui.js", "workspace.js", "workspace.css", "production.js", "production.css", "visual.css", "hardware-workspace.js", "hardware-workspace.css", "maintenance-ui.js", "maintenance-ui.css", "theme.css", "readiness-ui.js", "readiness-ui.css", "experience.js", "experience.css", "operations-ui.js", "operations-ui.css", "registry-ui.js", "delivery-ui.js", "persisted-telemetry.js", "physical-build-ui.js", "team-ui.js", "maintenance-exercises-ui.js", "incidents-ui.js", "incidents-ui.css", "edgeops-bench-concept.webp", "edgeops-facility-concept.webp", "architecture.js", "signin.css", "signin.js", "industrial-motor.svg", "industrial-plant.svg", "edgeops-motor-photo.jpg", "edgeops-factory-backdrop.jpg"}

@app.exception_handler(RequestValidationError)
async def validation_failure(request: Request, error: RequestValidationError):
    # Do not echo raw credentials/payloads or non-JSON NaN values in error responses.
    errors = [{key: item[key] for key in ("loc", "msg", "type")} for item in error.errors()]
    return JSONResponse({"detail": errors}, status_code=422, headers=SECURITY_HEADERS)


@app.get("/static/{asset}")
def public_asset(asset: str):
    if asset not in PUBLIC_ASSETS:
        raise HTTPException(404, "Not found")
    candidate = ROOT / asset
    if not candidate.is_file():
        raise HTTPException(404, "Asset not installed")
    return FileResponse(candidate)

# Canonical BOM identifiers supersede the old grouped HW slots.
from hardware_catalog import HARDWARE


def now_epoch() -> int:
    return int(time.time())


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 480_000)
    return "pbkdf2_sha256$480000$" + salt.hex() + "$" + digest.hex()


def password_matches(password: str, expected: str) -> bool:
    try:
        scheme, iterations, salt, digest = expected.split("$")
        if scheme != "pbkdf2_sha256" or int(iterations) < 300_000:
            return False
        calculated = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(calculated, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


@contextmanager
def database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DB_PATH), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db():
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL,
            disabled INTEGER NOT NULL DEFAULT 0)""")
        db.execute("""CREATE TABLE IF NOT EXISTS sessions(
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            csrf_hash TEXT NOT NULL, expires_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id))""")
        db.execute("""CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY, time_utc TEXT NOT NULL,
            actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS comparison_reviews(
            comparison_id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
            status TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT NOT NULL,
            reviewed_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS comparison_review_events(
            comparison_id TEXT NOT NULL, revision INTEGER NOT NULL,
            status TEXT NOT NULL, reviewer TEXT NOT NULL, note TEXT NOT NULL,
            reviewed_at TEXT NOT NULL, PRIMARY KEY(comparison_id,revision))""")
        incidents.init_schema(db)
        team_accounts.init_schema(db)
        maintenance_requests.init_schema(db)
        maintenance_exercises.init_schema(db)
        production_readiness.init_schema(db)
        acquisition_registry.init_schema(db)
        delivery_service.init_schema(db)
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (now_epoch(),))
        number = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if number == 0 and BOOTSTRAP_EMAIL and BOOTSTRAP_PASSWORD:
            if len(BOOTSTRAP_PASSWORD) < 14 or len(BOOTSTRAP_EMAIL) > 254 or "@" not in BOOTSTRAP_EMAIL:
                raise RuntimeError("Bootstrap admin needs a valid email and password of at least 14 characters")
            db.execute("INSERT INTO users(email,password_hash,role) VALUES(?,?,?)",
                       (BOOTSTRAP_EMAIL, password_hash(BOOTSTRAP_PASSWORD), "admin"))
            record_audit(db, BOOTSTRAP_EMAIL, "bootstrap", "local development admin created")


def record_audit(db: sqlite3.Connection, actor: str, action: str, detail: str):
    db.execute("INSERT INTO audit(time_utc,actor,action,detail) VALUES(?,?,?,?)",
               (datetime.now(timezone.utc).isoformat(), actor, action, detail[:240]))


@app.on_event("startup")
def startup():
    init_db()


def auth_context(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) != 64:
        return None
    with database() as db:
        row = db.execute("""SELECT u.id,u.email,u.role,u.disabled,s.csrf_hash,s.expires_at
            FROM sessions s JOIN users u ON u.id=s.user_id
            WHERE s.token_hash=?""", (token_hash(token),)).fetchone()
    if not row or row["disabled"] or row["expires_at"] <= now_epoch():
        return None
    return dict(row)


def require_user(request: Request):
    current = auth_context(request)
    if not current:
        raise HTTPException(401, "Authentication required")
    return current


def require_csrf(request: Request, current: dict):
    header = request.headers.get("x-edgeops-csrf", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not header or not cookie or not hmac.compare_digest(header, cookie):
        raise HTTPException(403, "CSRF token missing or invalid")
    if not hmac.compare_digest(token_hash(header), current["csrf_hash"]):
        raise HTTPException(403, "CSRF token missing or invalid")


def set_session(response: Response, token: str, csrf: str):
    response.set_cookie(COOKIE, token, httponly=True, secure=HTTPS_ONLY,
                        samesite="strict", max_age=SESSION_SECONDS, path="/")
    # JS must read CSRF token for same-origin mutation requests.
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=HTTPS_ONLY,
                        samesite="strict", max_age=SESSION_SECONDS, path="/")


def clear_session(response: Response):
    response.delete_cookie(COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class SyntheticTelemetryInput(BaseModel):
    """Explicit synthetic-only event; real sensor ingestion is not supported."""
    event_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    asset_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    captured_at: datetime
    vibration_mm_s: float = Field(ge=0, le=500, allow_inf_nan=False)
    temperature_c: float = Field(ge=-40, le=180, allow_inf_nan=False)
    current_a: float = Field(ge=0, le=100, allow_inf_nan=False)
    provenance: Literal["synthetic-demo"]

class AlertAction(BaseModel):
    alert_id: str = Field(pattern=r"^AL-[0-9]{4}$", max_length=7)
    note: str = Field(default="", max_length=200)


# Small single-process throttle ONLY; needs distributed rate limiting at scale.
FAILED_LOGINS: dict[str, list[int]] = {}


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
            return JSONResponse({"detail": "Origin mismatch"}, status_code=403, headers=SECURITY_HEADERS)
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


app.add_middleware(RequestBodyLimit, max_bytes=MAX_BODY_BYTES)


@app.get("/")
def root(request: Request):
    return RedirectResponse("/app" if auth_context(request) else "/signin", status_code=303)


@app.get("/signin")
def signin(request: Request):
    if auth_context(request):
        return RedirectResponse("/app", status_code=303)
    return FileResponse(ROOT / "signin.html")


@app.get("/app")
def main_app(request: Request):
    if not auth_context(request):
        return RedirectResponse("/signin", status_code=303)
    return FileResponse(ROOT / "index.html")


@app.post("/api/auth/login")
def login(request: Request, body: LoginInput):
    email = body.email.strip().lower()
    # Hash email rather than store raw passwords or arbitrary client identifiers.
    client = request.client.host if request.client else "unknown"
    ipkey = token_hash(client + "|" + email)
    window = now_epoch() - 900
    attempts = [x for x in FAILED_LOGINS.get(ipkey, []) if x > window]
    if len(attempts) >= 5:
        raise HTTPException(429, "Too many attempts; retry later")
    with database() as db:
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        # Do expensive KDF for nonexistent accounts to limit timing differences.
        dummy = "pbkdf2_sha256$480000$" + ("00" * 16) + "$" + ("00" * 32)
        ok = password_matches(body.password, user["password_hash"] if user else dummy)
        if not user or user["disabled"] or not ok:
            FAILED_LOGINS[ipkey] = attempts + [now_epoch()]
            record_audit(db, "unauthenticated", "login_failed", "invalid credentials")
            # Persist the denial before propagating the HTTP exception.
            db.commit()
            raise HTTPException(401, "Invalid email or password")
        # Password hashing can overlap a credential/access change. Serialize the
        # final credential check with session issuance so an old password cannot
        # create a new session after a successful password rotation.
        db.execute("BEGIN IMMEDIATE")
        latest = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
        if not latest or latest["disabled"] or latest["password_hash"] != user["password_hash"]:
            FAILED_LOGINS[ipkey] = attempts + [now_epoch()]
            record_audit(db, "unauthenticated", "login_failed", "invalid credentials")
            db.commit()
            raise HTTPException(401, "Invalid email or password")
        user = latest
        FAILED_LOGINS.pop(ipkey, None)
        token = secrets.token_hex(32)
        csrf = secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions(token_hash,user_id,csrf_hash,expires_at) VALUES(?,?,?,?)",
                   (token_hash(token), user["id"], token_hash(csrf), now_epoch() + SESSION_SECONDS))
        record_audit(db, email, "login", "authenticated local browser session")
    response = JSONResponse({"ok": True, "role": user["role"], "redirect": "/app"})
    set_session(response, token, csrf)
    return response


@app.get("/api/me")
def me(request: Request):
    current = require_user(request)
    return {"email": current["email"], "role": current["role"],
            "mode": "synthetic", "session_expires_at": current["expires_at"]}


@app.post("/api/auth/logout")
def logout(request: Request):
    current = require_user(request)
    require_csrf(request, current)
    with database() as db:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(request.cookies[COOKIE]),))
        record_audit(db, current["email"], "logout", "local browser session ended")
    response = JSONResponse({"ok": True})
    clear_session(response)
    return response


@app.get("/api/hardware")
def hardware(request: Request):
    require_user(request)
    return {"mode": "declared-order-inventory", "confirmed_hardware_count": 0, "named_category_count": 30,
            "catalog_version": "production-design-bom-v1",
            "slots_total": 30, "purchased_count": None,
            "ordered_count_user_reported": 30, "order_reported_on": "2026-11-20",
            "devices": [{"id": i, "name": n, "purpose": p, "category": c,
                         "confirmed_inventory_name": False, "connected": False,
                         "lifecycle": "ordered-user-reported", "purchase_verified": False}
                        for i, n, p, c in HARDWARE]}


@app.get("/health/live")
def liveness():
    return {"status": "alive", "mode": "local-development"}


@app.get("/health/ready")
def readiness_probe(response: Response):
    available = operations.database_status(DB_PATH)["status"] == "available"
    response.status_code = 200 if available else 503
    return {"status": "available" if available else "unavailable", "production_ready": False}


@app.get("/api/system/diagnostics")
def system_diagnostics(request: Request):
    current = require_user(request)
    if current["role"] not in ("admin", "auditor"):
        raise HTTPException(403, "Role not authorized")
    return operations.diagnostics(DB_PATH, ROOT)


@app.get("/api/system/health")
def health(request: Request):
    require_user(request)
    return {"status": "local-demo", "hardware_connected": False,
            "telemetry_mode": "synthetic-browser-fixtures", "model_deployed": False,
            "actuators_enabled": False, "security_approval": "open",
            "physical_safety_gate": "blocking"}


@app.get("/api/audit")
def audit(request: Request, limit: int = 50):
    current = require_user(request)
    if current["role"] not in ("admin", "auditor"):
        raise HTTPException(403, "Role not authorized")
    limit = max(1, min(limit, 100))
    with database() as db:
        entries = db.execute("SELECT time_utc,actor,action,detail FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"entries": [dict(e) for e in entries], "mode": "local-auth-audit-only"}


@app.post("/api/alerts/acknowledge")
def acknowledge(request: Request, body: AlertAction):
    current = require_user(request)
    require_csrf(request, current)
    if current["role"] not in ("admin", "operator"):
        raise HTTPException(403, "Role not authorized")
    # No real alarm mutation. Persist only audit record of a synthetic UI action.
    with database() as db:
        record_audit(db, current["email"], "demo_alert_ack", body.alert_id)
    return {"ok": True, "mode": "demo-audit-only", "persistent_alarm_state": False}


@app.post("/api/synthetic-telemetry", status_code=201)
def ingest_synthetic_telemetry(request: Request, event: SyntheticTelemetryInput, response: Response):
    """Authenticated local fixture ingestion only; no hardware or model outputs."""
    current = require_user(request)
    require_csrf(request, current)
    if current["role"] != "admin":
        raise HTTPException(403, "Admin role required for synthetic fixture ingestion")
    if event.captured_at.tzinfo is None or event.captured_at.utcoffset() is None:
        raise HTTPException(422, "captured_at must contain a timezone offset")
    try:
        created, stored = telemetry_store.append_event(event)
    except ValueError as error:
        raise HTTPException(409, str(error))
    response.status_code = 201 if created else 200
    return {"inserted": created, "event": stored, "mode": "synthetic-demo", "model_deployed": False}


@app.get("/api/synthetic-telemetry")
def list_synthetic_telemetry(request: Request, asset_id: str | None = None, limit: int = 100):
    require_user(request)
    if asset_id is not None and (len(asset_id) > 64 or not asset_id.replace("_", "").replace("-", "").isalnum()):
        raise HTTPException(422, "Invalid asset_id")
    return {"events": telemetry_store.read_events(asset_id=asset_id, limit=limit),
            "provenance": "synthetic-demo", "model_deployed": False, "hardware_connected": False}


@app.get("/api/offline-experiments")
def list_offline_experiments(request: Request, limit: int = 20):
    """Read verified *local synthetic* run summaries; never expose raw datasets."""
    require_user(request)
    from experiment_registry import verify_experiment
    root = Path(os.environ.get(
        "EDGEOPS_OFFLINE_EXPERIMENT_ROOT", str(ROOT / ".local" / "experiments")
    )).resolve()
    if not root.is_dir() or not (root / "runs").is_dir():
        return {"experiments": [], "mode": "synthetic-offline-only",
                "model_deployed": False, "hardware_connected": False}
    limit = max(1, min(50, limit))
    result = []
    # Sorted identifiers, never caller-provided filenames or unverified JSON.
    for path in sorted((root / "runs").glob("*.json"))[:500]:
        if len(result) >= limit:
            break
        try:
            verified = verify_experiment(root, path.stem)
        except (ValueError, OSError, TypeError, KeyError):
            # Fail closed: do not display unverified or tampered reports.
            continue
        report = verified["report"]
        result.append({
            "run_id": path.stem,
            "dataset_sha256": report["dataset_sha256"],
            "model_kind": verified["model"].get("model_kind", "offline-baseline"),
            "test_count": report["counts"]["test"],
            "precision": report["test_metrics"]["precision"],
            "recall": report["test_metrics"]["recall"],
            "f1": report["test_metrics"]["f1"],
            "evaluation_scope": report["evaluation_scope"],
            "deployment_status": "not-deployed",
        })
    return {"experiments": result, "mode": "synthetic-offline-only",
            "model_deployed": False, "hardware_connected": False}


def comparison_root():
    return Path(os.environ.get("EDGEOPS_OFFLINE_EXPERIMENT_ROOT",
                               str(ROOT / ".local" / "experiments"))).resolve()


def comparison_review(db, comparison_id):
    row = db.execute("SELECT * FROM comparison_reviews WHERE comparison_id=?",
                     (comparison_id,)).fetchone()
    return dict(row) if row else {"status": "pending", "revision": 0,
                                 "reviewer": None, "note": "", "reviewed_at": None}


@app.get("/api/model-comparisons")
def list_model_comparisons(request: Request, limit: int = 20):
    current = require_user(request)
    from comparison_registry import verify_comparison
    result = []
    with database() as db:
        for path in sorted((comparison_root() / "comparisons").glob("*.json"))[:500]:
            if len(result) >= max(1, min(50, limit)):
                break
            try:
                report = verify_comparison(comparison_root(), path.stem)
                outcome = report["result"]
                result.append({"comparison_id": path.stem,
                               "dataset_sha256": report["dataset_sha256"],
                               "split": outcome["split"], "models": outcome["models"],
                               "review": comparison_review(db, path.stem),
                               "review_history": [dict(row) for row in db.execute(
                                   "SELECT revision,status,reviewer,note,reviewed_at FROM comparison_review_events "
                                   "WHERE comparison_id=? ORDER BY revision DESC LIMIT 20", (path.stem,))]})
            except (ValueError, OSError, TypeError, KeyError, AttributeError):
                continue
    return {"comparisons": result, "can_review": current["role"] == "admin",
            "mode": "synthetic-offline-only", "model_deployed": False,
            "hardware_connected": False, "approval_scope": "offline-report-only"}


class ComparisonReviewInput(BaseModel):
    status: Literal["approved", "rejected", "pending"]
    note: str = Field(min_length=1, max_length=500)
    expected_revision: int = Field(ge=0, strict=True)


@app.post("/api/model-comparisons/{comparison_id}/review")
def review_model_comparison(comparison_id: str, body: ComparisonReviewInput, request: Request):
    current = require_user(request)
    require_csrf(request, current)
    if current["role"] != "admin":
        raise HTTPException(403, "Admin role required for offline report review")
    if not body.note.strip():
        raise HTTPException(422, "A review note is required")
    from comparison_registry import check_id, verify_comparison
    try:
        check_id(comparison_id)
    except ValueError as error:
        raise HTTPException(422, str(error))
    try:
        verify_comparison(comparison_root(), comparison_id)
    except (ValueError, OSError, TypeError, KeyError, AttributeError):
        raise HTTPException(409, "Comparison unavailable or failed integrity verification; refresh reports")
    with database() as db:
        # Serialize revision check and update, including the matching audit event.
        db.execute("BEGIN IMMEDIATE")
        previous = comparison_review(db, comparison_id)
        if previous["revision"] != body.expected_revision:
            raise HTTPException(409, "Review changed; refresh before submitting again")
        reviewed_at = datetime.now(timezone.utc).isoformat()
        db.execute("""INSERT INTO comparison_reviews VALUES(?,?,?,?,?,?)
            ON CONFLICT(comparison_id) DO UPDATE SET revision=excluded.revision,
            status=excluded.status, reviewer=excluded.reviewer,
            note=excluded.note, reviewed_at=excluded.reviewed_at""",
                   (comparison_id, previous["revision"] + 1, body.status,
                    current["email"], body.note.strip(), reviewed_at))
        db.execute("INSERT INTO comparison_review_events VALUES(?,?,?,?,?,?)",
                   (comparison_id, previous["revision"] + 1, body.status,
                    current["email"], body.note.strip(), reviewed_at))
        record_audit(db, current["email"], "offline_comparison_review",
                     json.dumps({"comparison_id": comparison_id,
                                 "revision": previous["revision"] + 1,
                                 "status": body.status}))
        review = comparison_review(db, comparison_id)
    return {"review": review, "approval_scope": "offline-report-only", "model_deployed": False,
            "hardware_connected": False}


incidents.install_routes(app, database, require_user, require_csrf, record_audit)

maintenance_requests.install_routes(app, database, require_user, require_csrf, record_audit)

maintenance_exercises.install_routes(app, database, require_user, require_csrf, record_audit)

production_readiness.install_routes(app, database, require_user, require_csrf, record_audit)

acquisition_registry.install_routes(app, database, require_user, require_csrf, record_audit)

delivery_service.install_routes(app, database, require_user, require_csrf, record_audit, DB_PATH.parent / "delivery-spool.sqlite3")

observation_queries.install_routes(app, database, require_user)

physical_build.install_routes(app, require_user, ROOT)

team_accounts.install_routes(app, database, require_user, require_csrf, password_hash, password_matches, record_audit)
