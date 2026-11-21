"""Authenticated, synthetic-only planning requests. No equipment authorization."""
from datetime import datetime, timezone
import hashlib
import json
import secrets
import time

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

ASSETS = {"MTR-001", "PMP-004", "FAN-002", "MTR-006", "CMP-003", "MTR-002",
          "PMP-001", "FAN-001", "MTR-003", "PMP-002", "MTR-004", "FAN-003"}
STATUSES = ("draft", "submitted", "approved", "rejected")
READ_ROLES = ("admin", "operator", "auditor")
WRITE_ROLES = ("admin", "operator")
BOUNDARY = {"scope": "local-synthetic-planning", "equipment_authorized": False,
            "hardware_connected": False, "execution_enabled": False}


class PlanFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str
    title: str = Field(min_length=5, max_length=120)
    observation: str = Field(min_length=10, max_length=2000)
    proposal: str = Field(min_length=10, max_length=2000)
    evidence_refs: str = Field(default="", max_length=1000)
    priority: str = "medium"

    @field_validator("asset_id")
    @classmethod
    def synthetic_asset(cls, value):
        if value not in ASSETS:
            raise ValueError("Select a synthetic workspace asset")
        return value

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, value):
        if value not in ("low", "medium", "high", "critical"):
            raise ValueError("Unknown planning priority")
        return value

    @field_validator("title", "observation", "proposal", "evidence_refs")
    @classmethod
    def trim_fields(cls, value, info):
        value = value.strip()
        minimum = {"title": 5, "observation": 10, "proposal": 10}.get(info.field_name, 0)
        if len(value) < minimum:
            raise ValueError(f"Enter at least {minimum} non-whitespace characters")
        return value


class CreatePlan(PlanFields):
    request_key: str = Field(pattern=r"^[0-9a-f]{32}$")


class EditPlan(PlanFields):
    expected_revision: int = Field(ge=1, strict=True)


class DecidePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)
    action: str
    note: str = Field(min_length=10, max_length=800)

    @field_validator("action")
    @classmethod
    def valid_action(cls, value):
        if value not in ("submit", "withdraw", "approve", "reject"):
            raise ValueError("Unknown planning action")
        return value

    @field_validator("note")
    @classmethod
    def nonblank_note(cls, value):
        if len(value.strip()) < 10:
            raise ValueError("Explain the decision in at least 10 characters")
        return value.strip()


def init_schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS maintenance_requests(
        id TEXT PRIMARY KEY, creator_id INTEGER NOT NULL REFERENCES users(id),
        creator_email TEXT NOT NULL, request_key TEXT NOT NULL, creation_hash TEXT NOT NULL,
        asset_id TEXT NOT NULL, title TEXT NOT NULL, observation TEXT NOT NULL,
        proposal TEXT NOT NULL, evidence_refs TEXT NOT NULL, priority TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('draft','submitted','approved','rejected')),
        revision INTEGER NOT NULL, reviewed_revision INTEGER, reviewer_email TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(creator_id,request_key))""")
    db.execute("""CREATE TABLE IF NOT EXISTS maintenance_request_events(
        request_id TEXT NOT NULL REFERENCES maintenance_requests(id), revision INTEGER NOT NULL,
        action TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id),
        actor_email TEXT NOT NULL, note TEXT NOT NULL, time_utc TEXT NOT NULL,
        snapshot_json TEXT NOT NULL, PRIMARY KEY(request_id,revision))""")
    db.execute("CREATE INDEX IF NOT EXISTS maintenance_creator ON maintenance_requests(creator_id,updated_at)")


def fresh_actor(db, current):
    """Recheck revocation and identity while the write transaction owns its lock."""
    row = db.execute("""SELECT u.id,u.email,u.role FROM users u JOIN sessions s ON s.user_id=u.id
        WHERE u.id=? AND u.disabled=0 AND s.csrf_hash=? AND s.expires_at>?""",
                     (current["id"], current["csrf_hash"], int(time.time()))).fetchone()
    if not row:
        raise HTTPException(401, "Session is no longer authorized")
    return dict(row)


def require_role(actor, roles):
    if actor["role"] not in roles:
        raise HTTPException(403, "This account cannot perform that planning action")


def visible_plan(db, plan_id, actor):
    require_role(actor, READ_ROLES)
    row = db.execute("SELECT * FROM maintenance_requests WHERE id=?", (plan_id,)).fetchone()
    if not row or (actor["role"] == "operator" and row["creator_id"] != actor["id"]):
        raise HTTPException(404, "Planning request not found")
    return dict(row)


def present(row, actor):
    data = {key: value for key, value in row.items() if key not in ("request_key", "creation_hash", "creator_id")}
    owner = row["creator_id"] == actor["id"] and actor["role"] in WRITE_ROLES
    data["actions"] = {"edit": owner and row["status"] != "submitted",
                       "submit": owner and row["status"] == "draft",
                       "withdraw": owner and row["status"] == "submitted",
                       "review": actor["role"] == "admin" and row["creator_id"] != actor["id"] and row["status"] == "submitted"}
    data["is_creator"] = row["creator_id"] == actor["id"]
    data["provenance"] = "synthetic-planning"
    return data


def detail(db, row, actor):
    from incidents import plan_source
    from maintenance_exercises import summary
    events = db.execute("""SELECT revision,action,actor_email,note,time_utc
        FROM maintenance_request_events WHERE request_id=? ORDER BY revision DESC""", (row["id"],)).fetchall()
    return {"request": present(row, actor), "history": [dict(event) for event in events],
            "source_incident": plan_source(db, row['id'], actor), **summary(db, row, actor), **BOUNDARY}


def append_event(db, row, actor, action, note, record_audit):
    # Snapshot, decision and audit commit together. History is never rewritten by edits.
    snapshot = {key: value for key, value in row.items() if key not in ("creation_hash", "request_key")}
    db.execute("INSERT INTO maintenance_request_events VALUES(?,?,?,?,?,?,?,?)",
               (row["id"], row["revision"], action, actor["id"], actor["email"], note,
                row["updated_at"], json.dumps(snapshot, sort_keys=True)))
    record_audit(db, actor["email"], "maintenance_planning_" + action,
                 json.dumps({"request_id": row["id"], "revision": row["revision"], "scope": BOUNDARY["scope"]}))


def install_routes(app, database, require_user, require_csrf, record_audit):
    @app.get("/api/maintenance-requests")
    def list_plans(request: Request, status: str = "all", q: str = Query(default="", max_length=160),
                   offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=50)):
        actor = require_user(request)
        require_role(actor, READ_ROLES)
        if status not in ("all", *STATUSES):
            raise HTTPException(422, "Unknown planning status")
        scope = "creator_id=?" if actor["role"] == "operator" else "1=1"
        scope_params = [actor["id"]] if actor["role"] == "operator" else []
        where, params = scope, list(scope_params)
        if status != "all":
            where += " AND status=?"
            params.append(status)
        if q.strip():
            # Bind the query and treat LIKE metacharacters as literal user input.
            query = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where += " AND (title LIKE ? ESCAPE '\\' OR asset_id LIKE ? ESCAPE '\\')"
            params.extend([query, query])
        with database() as db:
            db.execute("BEGIN")
            counts = {state: 0 for state in STATUSES}
            for row in db.execute("SELECT status,count(*) AS n FROM maintenance_requests WHERE " + scope + " GROUP BY status", scope_params):
                counts[row["status"]] = row["n"]
            total = db.execute("SELECT count(*) FROM maintenance_requests WHERE " + where, params).fetchone()[0]
            rows = db.execute("SELECT * FROM maintenance_requests WHERE " + where + " ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
        return {"requests": [present(dict(row), actor) for row in rows], "counts": counts,
                "total": total, "offset": offset, "limit": limit, "can_create": actor["role"] in WRITE_ROLES,
                "current_user": actor["email"], **BOUNDARY}

    @app.get("/api/maintenance-requests/{plan_id}")
    def get_plan(plan_id: str, request: Request):
        actor = require_user(request)
        with database() as db:
            db.execute("BEGIN")
            return detail(db, visible_plan(db, plan_id, actor), actor)

    @app.post("/api/maintenance-requests")
    def create_plan(body: CreatePlan, request: Request):
        current = require_user(request)
        require_csrf(request, current)
        fields = body.model_dump(exclude={"request_key"})
        digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            actor = fresh_actor(db, current)
            require_role(actor, WRITE_ROLES)
            existing = db.execute("SELECT * FROM maintenance_requests WHERE creator_id=? AND request_key=?", (actor["id"], body.request_key)).fetchone()
            if existing:
                if existing["creation_hash"] != digest:
                    raise HTTPException(409, "This save key already belongs to a different draft; refresh the queue before creating another")
                return {**detail(db, dict(existing), actor), "created": False}
            now = datetime.now(timezone.utc).isoformat()
            plan_id = secrets.token_hex(16)
            db.execute("""INSERT INTO maintenance_requests(id,creator_id,creator_email,request_key,
                creation_hash,asset_id,title,observation,proposal,evidence_refs,priority,status,revision,
                created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,'draft',1,?,?)""",
                       (plan_id, actor["id"], actor["email"], body.request_key, digest, fields["asset_id"],
                        fields["title"], fields["observation"], fields["proposal"], fields["evidence_refs"], fields["priority"], now, now))
            row = visible_plan(db, plan_id, actor)
            append_event(db, row, actor, "created", "Local synthetic planning draft created.", record_audit)
            return {**detail(db, row, actor), "created": True}

    @app.get("/api/maintenance-requests/{plan_id}/revisions/{revision}")
    def historical_plan(plan_id: str, revision: int, request: Request):
        actor = require_user(request)
        with database() as db:
            db.execute("BEGIN")
            visible_plan(db, plan_id, actor)
            event = db.execute("SELECT snapshot_json FROM maintenance_request_events WHERE request_id=? AND revision=?", (plan_id, revision)).fetchone()
            if not event:
                raise HTTPException(404, "Planning revision not found")
            snapshot = json.loads(event["snapshot_json"])
            snapshot.pop("creator_id", None)
            from incidents import plan_source
            return {"snapshot": snapshot, "read_only": True, "source_incident": plan_source(db, plan_id, actor), **BOUNDARY}

    @app.put("/api/maintenance-requests/{plan_id}")
    def edit_plan(plan_id: str, body: EditPlan, request: Request):
        current = require_user(request)
        require_csrf(request, current)
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            actor = fresh_actor(db, current)
            require_role(actor, WRITE_ROLES)
            row = visible_plan(db, plan_id, actor)
            if row["creator_id"] != actor["id"]:
                raise HTTPException(403, "Only the request creator can revise this plan")
            if row["revision"] != body.expected_revision:
                raise HTTPException(409, "The request changed; reload its latest revision before saving")
            if row["status"] == "submitted":
                raise HTTPException(409, "Withdraw the submitted request before editing")
            fields = body.model_dump(exclude={"expected_revision"})
            from incidents import plan_source
            source = plan_source(db, plan_id, actor)
            if source and fields['asset_id'] != source['snapshot']['asset_id']:
                raise HTTPException(409, 'A linked plan must retain the source incident asset')
            now = datetime.now(timezone.utc).isoformat()
            db.execute("""UPDATE maintenance_requests SET asset_id=?,title=?,observation=?,proposal=?,
                evidence_refs=?,priority=?,status='draft',reviewed_revision=NULL,reviewer_email=NULL,
                revision=revision+1,updated_at=? WHERE id=?""",
                       (fields["asset_id"], fields["title"], fields["observation"], fields["proposal"], fields["evidence_refs"], fields["priority"], now, plan_id))
            row = visible_plan(db, plan_id, actor)
            append_event(db, row, actor, "edited", "Plan revised; any prior review decision is invalid for this draft.", record_audit)
            return detail(db, row, actor)

    @app.post("/api/maintenance-requests/{plan_id}/actions")
    def decide_plan(plan_id: str, body: DecidePlan, request: Request):
        current = require_user(request)
        require_csrf(request, current)
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            actor = fresh_actor(db, current)
            require_role(actor, WRITE_ROLES)
            row = visible_plan(db, plan_id, actor)
            if row["revision"] != body.expected_revision:
                raise HTTPException(409, "The request changed; reload its latest revision before deciding")
            if body.action in ("submit", "withdraw"):
                if actor["id"] != row["creator_id"]:
                    raise HTTPException(403, "Only the creator can submit or withdraw this plan")
                expected = "draft" if body.action == "submit" else "submitted"
                if row["status"] != expected:
                    raise HTTPException(409, "That action is unavailable in the current planning state")
                status = "submitted" if body.action == "submit" else "draft"
                reviewed_revision, reviewer = None, None
            else:
                require_role(actor, ("admin",))
                if actor["id"] == row["creator_id"]:
                    raise HTTPException(403, "Independent review required: the creator cannot approve or reject their own plan")
                if row["status"] != "submitted":
                    raise HTTPException(409, "Only a submitted revision can be reviewed")
                status = "approved" if body.action == "approve" else "rejected"
                reviewed_revision, reviewer = row["revision"], actor["email"]
            db.execute("""UPDATE maintenance_requests SET status=?,revision=revision+1,reviewed_revision=?,
                reviewer_email=?,updated_at=? WHERE id=?""", (status, reviewed_revision, reviewer,
                datetime.now(timezone.utc).isoformat(), plan_id))
            row = visible_plan(db, plan_id, actor)
            append_event(db, row, actor, status if body.action != "withdraw" else "withdrawn", body.note, record_audit)
            return detail(db, row, actor)
