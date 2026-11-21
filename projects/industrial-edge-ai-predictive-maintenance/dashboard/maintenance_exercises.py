"""Synthetic maintenance documentation exercises, never field-work authorization."""
from datetime import datetime, timezone
import json
import secrets
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
import maintenance_requests as plans

BOUNDARY = {'scope': 'synthetic-maintenance-exercise', 'source_type': 'synthetic',
            'hardware_connected': False, 'equipment_authorized': False, 'execution_enabled': False,
            'physical_work_verified': False, 'production_ready': False}
MAX_PER_PLAN, MAX_REVISIONS = 50, 100


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CreateExercise(StrictModel):
    expected_plan_revision: int = Field(strict=True, ge=1)


class EditExercise(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    work_note: str = Field(strict=True, min_length=10, max_length=2000)
    outcome: str = Field(strict=True, min_length=10, max_length=2000)
    evidence_refs: str = Field(strict=True, max_length=1000)


class ExerciseAction(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    action: Literal['submit', 'withdraw', 'verify', 'reject']
    note: str = Field(strict=True, min_length=10, max_length=800)


def init_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS maintenance_exercises(
        id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES maintenance_requests(id),
        plan_revision INTEGER NOT NULL, creator_id INTEGER NOT NULL REFERENCES users(id),
        creator_email TEXT NOT NULL, plan_snapshot_json TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('draft','submitted','verified','rejected')),
        revision INTEGER NOT NULL, work_note TEXT NOT NULL, outcome TEXT NOT NULL,
        evidence_refs TEXT NOT NULL, reviewer_email TEXT, reviewed_revision INTEGER,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(plan_id,plan_revision))''')
    db.execute('''CREATE TABLE IF NOT EXISTS maintenance_exercise_events(
        exercise_id TEXT NOT NULL REFERENCES maintenance_exercises(id), revision INTEGER NOT NULL,
        action TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), actor_email TEXT NOT NULL,
        note TEXT NOT NULL, time_utc TEXT NOT NULL, snapshot_json TEXT NOT NULL,
        PRIMARY KEY(exercise_id,revision))''')


def plan_is_current(plan, row):
    return plan['status'] == 'approved' and plan['revision'] == row['plan_revision']


def present(row, actor, plan):
    data = {key: value for key, value in dict(row).items() if key not in ('creator_id', 'plan_snapshot_json')}
    current = plan_is_current(plan, row); owner = row['creator_id'] == actor['id'] and actor['role'] in plans.WRITE_ROLES
    capacity = row['revision'] < MAX_REVISIONS
    data['plan_changed_since_capture'] = not current
    data['actions'] = {'edit': current and capacity and owner and row['state'] != 'submitted',
        'submit': current and row['revision'] < MAX_REVISIONS - 1 and owner and row['state'] == 'draft',
        'withdraw': capacity and owner and row['state'] == 'submitted',
        'review': current and capacity and actor['role'] == 'admin' and row['creator_id'] != actor['id'] and row['state'] == 'submitted'}
    return data


def summary(db, plan, actor):
    rows = db.execute('SELECT * FROM maintenance_exercises WHERE plan_id=? ORDER BY plan_revision DESC LIMIT ?', (plan['id'], MAX_PER_PLAN)).fetchall()
    summaries = []
    for row in rows:
        item = present(row, actor, plan)
        summaries.append({key: item[key] for key in ('id','plan_id','plan_revision','creator_email','state','revision','plan_changed_since_capture')})
    return {'exercises': summaries,
            'can_create_exercise': actor['role'] in plans.WRITE_ROLES and actor['id'] == plan['creator_id']
                and plan['status'] == 'approved' and len(rows) < MAX_PER_PLAN
                and not any(row['plan_revision'] == plan['revision'] for row in rows)}


def visible(db, identifier, actor):
    plans.require_role(actor, plans.READ_ROLES)
    row = db.execute('SELECT * FROM maintenance_exercises WHERE id=?', (identifier,)).fetchone()
    if not row or actor['role'] == 'operator' and row['creator_id'] != actor['id']:
        raise HTTPException(404, 'Maintenance exercise not found')
    plan = plans.visible_plan(db, row['plan_id'], actor)
    return row, plan


def detail(db, row, actor, plan):
    history = db.execute('''SELECT revision,action,actor_email,note,time_utc,snapshot_json FROM maintenance_exercise_events
        WHERE exercise_id=? ORDER BY revision DESC LIMIT ?''', (row['id'], MAX_REVISIONS)).fetchall()
    events = []
    for item in history:
        event = dict(item); snapshot = json.loads(event.pop('snapshot_json'))
        event['record'] = {key: snapshot[key] for key in ('work_note','outcome','evidence_refs','state','reviewer_email','reviewed_revision')}
        events.append(event)
    return {'exercise': present(row, actor, plan), 'approved_plan_snapshot': json.loads(row['plan_snapshot_json']),
            'current_plan': {'id': plan['id'], 'revision': plan['revision'], 'status': plan['status']},
            'history': events, **BOUNDARY}


def append_event(db, row, actor, action, note, audit):
    snapshot = {key: value for key, value in dict(row).items() if key != 'creator_id'}
    db.execute('INSERT INTO maintenance_exercise_events VALUES(?,?,?,?,?,?,?,?)',
        (row['id'], row['revision'], action, actor['id'], actor['email'], note, row['updated_at'], json.dumps(snapshot, sort_keys=True)))
    audit(db, actor['email'], 'maintenance_exercise_' + action, json.dumps({'exercise_id': row['id'], 'revision': row['revision'], 'scope': BOUNDARY['scope']}))


def install_routes(app, database, require_user, require_csrf, audit):
    @app.post('/api/maintenance-requests/{plan_id}/exercises')
    def create(plan_id: str, body: CreateExercise, request: Request):
        current = require_user(request); require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = plans.fresh_actor(db, current); plans.require_role(actor, plans.WRITE_ROLES)
            plan = plans.visible_plan(db, plan_id, actor)
            if plan['creator_id'] != actor['id']: raise HTTPException(403, 'Only the plan creator can prepare its exercise record')
            prior = db.execute('SELECT * FROM maintenance_exercises WHERE plan_id=? AND plan_revision=?', (plan_id, body.expected_plan_revision)).fetchone()
            if prior: return {**detail(db, prior, actor, plan), 'created': False}
            if plan['status'] != 'approved' or plan['revision'] != body.expected_plan_revision:
                raise HTTPException(409, 'Prepare an exercise only from the current independently approved plan revision')
            if db.execute('SELECT count(*) FROM maintenance_exercises WHERE plan_id=?', (plan_id,)).fetchone()[0] >= MAX_PER_PLAN:
                raise HTTPException(409, 'Exercise capacity reached; existing records remain retained')
            from incidents import plan_source
            snapshot = plans.present(plan, actor); snapshot.pop('actions')
            snapshot.pop('is_creator', None)
            snapshot['source_incident'] = plan_source(db, plan_id, actor)
            now = datetime.now(timezone.utc).isoformat(); identifier = secrets.token_hex(16)
            db.execute('''INSERT INTO maintenance_exercises VALUES(?,?,?,?,?,?,'draft',1,?,'','',NULL,NULL,?,?)''',
                (identifier, plan_id, plan['revision'], actor['id'], actor['email'], json.dumps(snapshot, sort_keys=True),
                 'Synthetic documentation exercise only; no physical work is recorded or authorized.', now, now))
            row, plan = visible(db, identifier, actor)
            append_event(db, row, actor, 'created', 'Exercise bound to an independently approved synthetic planning revision.', audit)
            return {**detail(db, row, actor, plan), 'created': True}

    @app.get('/api/maintenance-exercises/{identifier}')
    def get(identifier: str, request: Request):
        actor = require_user(request)
        with database() as db:
            db.execute('BEGIN'); row, plan = visible(db, identifier, actor)
            return detail(db, row, actor, plan)

    @app.put('/api/maintenance-exercises/{identifier}')
    def edit(identifier: str, body: EditExercise, request: Request):
        current = require_user(request); require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = plans.fresh_actor(db, current); plans.require_role(actor, plans.WRITE_ROLES)
            row, plan = visible(db, identifier, actor)
            if actor['id'] != row['creator_id']: raise HTTPException(403, 'Only the exercise creator can revise its notes')
            if row['revision'] != body.expected_revision or not present(row, actor, plan)['actions']['edit']:
                raise HTTPException(409, 'Exercise or approved plan changed; reopen the current records before editing')
            db.execute('''UPDATE maintenance_exercises SET work_note=?,outcome=?,evidence_refs=?,state='draft',
                revision=revision+1,reviewer_email=NULL,reviewed_revision=NULL,updated_at=? WHERE id=?''',
                (body.work_note, body.outcome, body.evidence_refs, datetime.now(timezone.utc).isoformat(), identifier))
            row, plan = visible(db, identifier, actor)
            append_event(db, row, actor, 'edited', 'Exercise notes revised; previous review no longer applies to this revision.', audit)
            return detail(db, row, actor, plan)

    @app.post('/api/maintenance-exercises/{identifier}/actions')
    def act(identifier: str, body: ExerciseAction, request: Request):
        current = require_user(request); require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = plans.fresh_actor(db, current); plans.require_role(actor, plans.WRITE_ROLES)
            row, plan = visible(db, identifier, actor)
            if row['revision'] != body.expected_revision or row['revision'] >= MAX_REVISIONS:
                raise HTTPException(409, 'Exercise revision changed or history capacity reached')
            actions = present(row, actor, plan)['actions']
            permission = 'review' if body.action in ('verify','reject') else body.action
            if not actions[permission]:
                if body.action in ('verify','reject') and actor['id'] == row['creator_id']:
                    raise HTTPException(403, 'An independent administrator must review this exercise')
                raise HTTPException(409, 'This action is unavailable for the current exercise, account or approved plan')
            if body.action == 'submit' and (len(row['outcome'].strip()) < 10 or not row['evidence_refs'].strip()):
                raise HTTPException(422, 'Record an exercise outcome and evidence references before submission')
            state = {'submit':'submitted','withdraw':'draft','verify':'verified','reject':'rejected'}[body.action]
            reviewed = row['revision'] if body.action in ('verify','reject') else None
            reviewer = actor['email'] if reviewed is not None else None
            db.execute('''UPDATE maintenance_exercises SET state=?,revision=revision+1,reviewer_email=?,
                reviewed_revision=?,updated_at=? WHERE id=?''', (state, reviewer, reviewed, datetime.now(timezone.utc).isoformat(), identifier))
            row, plan = visible(db, identifier, actor)
            append_event(db, row, actor, body.action, body.note, audit)
            return detail(db, row, actor, plan)
