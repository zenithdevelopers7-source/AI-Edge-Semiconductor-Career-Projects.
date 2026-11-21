"""Saved synthetic incident exercises; no live detection, escalation or equipment effects."""
from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Literal

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from maintenance_requests import ASSETS, READ_ROLES, WRITE_ROLES, fresh_actor, require_role
import maintenance_requests as planning
import observation_queries as observations
from acquisition_registry import Binding

BOUNDARY = {'scope': 'local-synthetic-incidents', 'source_type': 'synthetic',
            'hardware_connected': False, 'equipment_authorized': False, 'production_ready': False,
            'automatic_detection': False, 'external_notifications_sent': False}
STATES = ('open', 'acknowledged', 'resolved')
CURRENT_SEVERITY_SQL = 'COALESCE((SELECT severity FROM incident_triage WHERE incident_id=synthetic_incidents.id),synthetic_incidents.severity)'
TRANSITIONS = {'acknowledge': ('open', 'acknowledged'), 'resolve': ('acknowledged', 'resolved'),
               'reopen': ('resolved', 'open')}
MAX_INCIDENTS, MAX_REVISIONS = 1000, 200
MAX_LINKS_PER_INCIDENT = 20
MAX_ATTACHED_OBSERVATIONS = 20


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CreateIncident(StrictModel):
    request_key: str = Field(pattern=r'^[0-9a-f]{32}$', strict=True)
    source_type: Literal['synthetic']
    asset_id: str = Field(strict=True)
    title: str = Field(min_length=5, max_length=120, strict=True)
    observation: str = Field(min_length=10, max_length=2000, strict=True)
    severity: Literal['info', 'watch', 'critical']
    evidence_refs: str = Field(default='', max_length=1000, strict=True)

    @field_validator('asset_id')
    @classmethod
    def known_asset(cls, value):
        if value not in ASSETS: raise ValueError('Select a synthetic workspace asset')
        return value


class IncidentAction(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    action: Literal['acknowledge', 'resolve', 'reopen']
    note: str = Field(min_length=10, max_length=800, strict=True)
    evidence_refs: str = Field(default='', max_length=1000, strict=True)


class ObservationIncident(StrictModel):
    request_key: str = Field(pattern=r'^[0-9a-f]{32}$', strict=True)
    event_key: str = Field(pattern=r'^[0-9a-f]{64}$', strict=True)
    content_hash: str = Field(pattern=r'^[0-9a-f]{64}$', strict=True)
    title: str = Field(strict=True, min_length=5, max_length=120)
    observation: str = Field(strict=True, min_length=10, max_length=2000)
    severity: Literal['info', 'watch', 'critical']


class ReviewSeverity(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    severity: Literal['info', 'watch', 'critical']
    note: str = Field(strict=True, min_length=10, max_length=800)


class AttachObservation(StrictModel):
    request_key: str = Field(pattern=r'^[0-9a-f]{32}$', strict=True)
    expected_revision: int = Field(strict=True, ge=1)
    event_key: str = Field(pattern=r'^[0-9a-f]{64}$', strict=True)
    content_hash: str = Field(pattern=r'^[0-9a-f]{64}$', strict=True)
    note: str = Field(strict=True, min_length=10, max_length=800)


class InvestigationUpdate(StrictModel):
    request_key: str = Field(pattern=r'^[0-9a-f]{32}$', strict=True)
    expected_revision: int = Field(strict=True, ge=1)
    kind: Literal['update', 'analysis', 'evidence']
    note: str = Field(strict=True, min_length=10, max_length=800)
    evidence_refs: str = Field(default='', strict=True, max_length=1000)


class FollowUp(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    due_at: str | None = Field(max_length=40, strict=True)
    note: str = Field(strict=True, min_length=10, max_length=800)

    @field_validator('due_at')
    @classmethod
    def utc_date(cls, value):
        if value is None: return None
        try:
            parsed=datetime.fromisoformat(value)
            if parsed.tzinfo is None or parsed.utcoffset() is None or not 2000<=parsed.year<=2100:
                raise ValueError()
            normalized=parsed.astimezone(timezone.utc)
            if not 2000<=normalized.year<=2100: raise ValueError()
            return normalized.isoformat(timespec='microseconds')
        except (ValueError, OverflowError):
            raise ValueError('Use a date from 2000 through 2100 with an explicit UTC offset')


class LinkedPlan(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    proposal: str = Field(strict=True, min_length=10, max_length=2000)


class AssignIncident(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    assignee_id: int | None = Field(strict=True, ge=1)
    note: str = Field(strict=True, min_length=10, max_length=800)


def init_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS synthetic_incidents(
        id TEXT PRIMARY KEY, creator_id INTEGER NOT NULL REFERENCES users(id), creator_email TEXT NOT NULL,
        request_key TEXT NOT NULL, creation_hash TEXT NOT NULL, asset_id TEXT NOT NULL,
        title TEXT NOT NULL, observation TEXT NOT NULL, severity TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('open','acknowledged','resolved')), revision INTEGER NOT NULL,
        evidence_refs TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(creator_id,request_key))''')
    db.execute('''CREATE TABLE IF NOT EXISTS synthetic_incident_events(
        incident_id TEXT NOT NULL REFERENCES synthetic_incidents(id), revision INTEGER NOT NULL,
        action TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id), actor_email TEXT NOT NULL,
        note TEXT NOT NULL, evidence_refs TEXT NOT NULL, time_utc TEXT NOT NULL, snapshot_json TEXT NOT NULL,
        PRIMARY KEY(incident_id,revision))''')
    db.execute('''CREATE TABLE IF NOT EXISTS incident_investigation_keys(
        incident_id TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id),
        request_key TEXT NOT NULL, request_hash TEXT NOT NULL, revision INTEGER NOT NULL,
        PRIMARY KEY(incident_id,actor_id,request_key),
        FOREIGN KEY(incident_id,revision) REFERENCES synthetic_incident_events(incident_id,revision))''')
    db.execute('''CREATE TABLE IF NOT EXISTS incident_observation_sources(
        incident_id TEXT PRIMARY KEY REFERENCES synthetic_incidents(id),
        event_key TEXT NOT NULL REFERENCES acquisition_observations(event_key),
        creator_id INTEGER NOT NULL REFERENCES users(id), snapshot_json TEXT NOT NULL,
        UNIQUE(creator_id,event_key))''')
    db.execute('''CREATE TABLE IF NOT EXISTS incident_observation_attachments(
        incident_id TEXT NOT NULL, event_key TEXT NOT NULL REFERENCES acquisition_observations(event_key),
        revision INTEGER NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id),
        request_key TEXT NOT NULL, request_hash TEXT NOT NULL, snapshot_json TEXT NOT NULL,
        PRIMARY KEY(incident_id,event_key), UNIQUE(incident_id,actor_id,request_key),
        FOREIGN KEY(incident_id,revision) REFERENCES synthetic_incident_events(incident_id,revision))''')
    db.execute('''CREATE TABLE IF NOT EXISTS incident_triage(
        incident_id TEXT PRIMARY KEY REFERENCES synthetic_incidents(id),
        severity TEXT NOT NULL CHECK(severity IN ('info','watch','critical')), updated_at TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS incident_creator_state ON synthetic_incidents(creator_id,state,updated_at)')
    db.execute('''CREATE TABLE IF NOT EXISTS incident_followups(
        incident_id TEXT PRIMARY KEY REFERENCES synthetic_incidents(id), due_at TEXT, updated_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS incident_assignments(
        incident_id TEXT PRIMARY KEY REFERENCES synthetic_incidents(id),
        assignee_id INTEGER REFERENCES users(id), assignee_email TEXT, updated_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS incident_plan_links(
        plan_id TEXT PRIMARY KEY REFERENCES maintenance_requests(id),
        incident_id TEXT NOT NULL REFERENCES synthetic_incidents(id),
        creator_id INTEGER NOT NULL REFERENCES users(id), incident_revision INTEGER NOT NULL,
        request_hash TEXT NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(incident_id,creator_id))''')


def plan_source(db, plan_id, actor):
    row = db.execute('''SELECT l.*,i.revision current_revision,i.state current_state,i.creator_id source_creator_id,
        a.assignee_id source_assignee_id
        FROM incident_plan_links l JOIN synthetic_incidents i ON i.id=l.incident_id
        LEFT JOIN incident_assignments a ON a.incident_id=i.id
        WHERE l.plan_id=?''', (plan_id,)).fetchone()
    if not row: return None
    accessible = actor['role'] in ('admin','auditor') or actor['id'] in (row['source_creator_id'],row['source_assignee_id'])
    return {'id': row['incident_id'], 'revision': row['incident_revision'],
            'snapshot': json.loads(row['snapshot_json']), 'current_accessible': accessible,
            'current_revision': row['current_revision'] if accessible else None,
            'current_state': row['current_state'] if accessible else None,
            'changed_since_capture': row['incident_revision'] != row['current_revision'] if accessible else None}


def linked_plans(db, incident_id, actor):
    where = ' AND p.creator_id=?' if actor['role'] == 'operator' else ''
    args = [incident_id, actor['id']] if actor['role'] == 'operator' else [incident_id]
    rows = db.execute('''SELECT p.id,p.title,p.status,p.revision,p.creator_email,l.incident_revision
        FROM incident_plan_links l JOIN maintenance_requests p ON p.id=l.plan_id
        WHERE l.incident_id=?''' + where + ' ORDER BY l.created_at,p.id LIMIT ?', [*args, MAX_LINKS_PER_INCIDENT]).fetchall()
    return [dict(row) for row in rows]


def assignment(db, incident_id):
    row = db.execute('''SELECT a.assignee_id,a.assignee_email,u.role,u.disabled
        FROM incident_assignments a LEFT JOIN users u ON u.id=a.assignee_id WHERE a.incident_id=?''', (incident_id,)).fetchone()
    if not row or row['assignee_id'] is None: return None
    return {'user_id': row['assignee_id'], 'email': row['assignee_email'],
            'eligible': row['role'] in WRITE_ROLES and not row['disabled']}


def controls_assignment(row, actor):
    return actor['role'] in WRITE_ROLES and (actor['role']=='admin' or row['creator_id']==actor['id'])


def followup(db, row, now=None):
    saved=db.execute('SELECT due_at FROM incident_followups WHERE incident_id=?',(row['id'],)).fetchone()
    due=saved['due_at'] if saved else None
    now=now or datetime.now(timezone.utc)
    status='none' if due is None else 'resolved' if row['state']=='resolved' else 'overdue' if datetime.fromisoformat(due)<=now else 'upcoming'
    return {'due_at':due,'status':status,'evaluated_at':now.isoformat(), 'clock_source':'local-service-clock'}


def current_severity(db, incident_id):
    row=db.execute('SELECT COALESCE(t.severity,i.severity) severity FROM synthetic_incidents i LEFT JOIN incident_triage t ON t.incident_id=i.id WHERE i.id=?',(incident_id,)).fetchone()
    return row['severity']


def present(row, actor, owner=None, follow_up=None, reviewed_severity=None):
    data = {key: value for key, value in dict(row).items() if key not in ('request_key','creation_hash','creator_id')}
    writable = actor['role'] in WRITE_ROLES and (actor['role'] == 'admin' or row['creator_id'] == actor['id'] or owner and owner['user_id']==actor['id'])
    data['initial_severity']=row['severity']
    data['current_severity']=reviewed_severity or row['severity']
    data['follow_up'] = follow_up
    data['can_set_follow_up'] = bool(writable and row['state']!='resolved' and row['revision']<MAX_REVISIONS)
    data['can_add_update'] = data['can_set_follow_up']
    data['assignment'] = owner
    data['can_assign'] = controls_assignment(row,actor) and row['state']!='resolved' and row['revision']<MAX_REVISIONS
    data['actions'] = [action for action, (start, _) in TRANSITIONS.items()
                       if writable and row['state'] == start and row['revision'] < MAX_REVISIONS]
    return data


def visible(db, incident_id, actor):
    require_role(actor, READ_ROLES)
    row = db.execute('SELECT * FROM synthetic_incidents WHERE id=?', (incident_id,)).fetchone()
    assigned = db.execute('SELECT 1 FROM incident_assignments WHERE incident_id=? AND assignee_id=?', (incident_id,actor['id'])).fetchone()
    if not row or actor['role'] == 'operator' and row['creator_id'] != actor['id'] and not assigned:
        raise HTTPException(404, 'Incident exercise not found')
    return row


def capture_observation(db, event_key, content_hash):
    source=db.execute('SELECT * FROM acquisition_observations WHERE event_key=?',(event_key,)).fetchone()
    if not source:raise HTTPException(404,'Committed synthetic observation not found')
    if source['content_hash']!=content_hash:raise HTTPException(409,'Observation identity changed; refresh its saved history')
    now=datetime.now(timezone.utc)
    snapshot=observations.present(source,now,60)
    sample=snapshot['observation']
    binding=db.execute('SELECT * FROM acquisition_bindings WHERE device_id=?',(source['device_id'],)).fetchone()
    if not binding or binding['site_id']!=sample['site_id'] or binding['asset_id']!=sample['asset_id'] or binding['revision']<source['binding_revision']:
        raise HTTPException(503,'Stored observation does not match its immutable test binding')
    if sample['asset_id'] not in ASSETS:
        raise HTTPException(422,'The test binding asset has no matching dashboard asset; no asset mapping was inferred')
    try:
        definition=Binding.model_validate_json(binding['definition']).model_dump()
        if any(definition[key]!=binding[key] for key in ('site_id','asset_id','device_id')):raise ValueError()
    except (ValueError,TypeError,KeyError):
        raise HTTPException(503,'Stored test binding definition failed its contract or identity checks')
    snapshot.pop('freshness');snapshot.pop('central_age_seconds')
    snapshot['channels']=observations.CHANNELS
    snapshot['captured_at']=now.isoformat()
    snapshot['binding_at_capture']={**definition,'revision':binding['revision'],'status':binding['status']}
    return snapshot


def observation_source(db, incident_id):
    source=db.execute('SELECT snapshot_json FROM incident_observation_sources WHERE incident_id=?',(incident_id,)).fetchone()
    return json.loads(source['snapshot_json']) if source else None


def observation_attachments(db, incident_id):
    return [{'revision':row['revision'],'snapshot':json.loads(row['snapshot_json'])} for row in db.execute(
        'SELECT revision,snapshot_json FROM incident_observation_attachments WHERE incident_id=? ORDER BY revision',(incident_id,))]


def detail(db, row, actor):
    events = db.execute('''SELECT revision,action,actor_email,note,evidence_refs,time_utc,snapshot_json
        FROM synthetic_incident_events WHERE incident_id=? ORDER BY revision DESC LIMIT ?''',
                        (row['id'], MAX_REVISIONS)).fetchall()
    own = db.execute('SELECT 1 FROM incident_plan_links WHERE incident_id=? AND creator_id=?', (row['id'], actor['id'])).fetchone()
    count = db.execute('SELECT count(*) FROM incident_plan_links WHERE incident_id=?', (row['id'],)).fetchone()[0]
    attachments=observation_attachments(db,row['id'])
    by_revision={item['revision']:item['snapshot'] for item in attachments}
    presented=present(row,actor,assignment(db,row['id']),followup(db,row),current_severity(db,row['id']))
    history=[]
    for item in events:
        entry=dict(item);snapshot=json.loads(entry.pop('snapshot_json'))
        entry['assignment_recorded']='assignment' in snapshot;entry['assignment']=snapshot.get('assignment')
        entry['follow_up_recorded']='follow_up' in snapshot;entry['follow_up']=snapshot.get('follow_up')
        entry['severity_recorded']='current_severity' in snapshot
        entry['initial_severity']=snapshot.get('initial_severity',snapshot.get('severity'))
        entry['current_severity']=snapshot.get('current_severity')
        entry['attached_observation']=by_revision.get(entry['revision'])
        history.append(entry)
    return {'incident': presented, 'history': history, 'can_review_severity':presented['can_add_update'],
            'attached_observations':attachments,
            'can_attach_observation':presented['can_add_update'] and len(attachments)<MAX_ATTACHED_OBSERVATIONS,
            'attached_observation_limit':MAX_ATTACHED_OBSERVATIONS,
            'source_observation': observation_source(db,row['id']),
            'linked_plans': linked_plans(db, row['id'], actor),
            'can_prepare_plan': actor['role'] in WRITE_ROLES and row['state'] != 'resolved' and not own and count < MAX_LINKS_PER_INCIDENT,
            **BOUNDARY}


def event(db, row, actor, action, note, evidence, audit):
    snapshot = present(row, actor, assignment(db,row['id']), followup(db,row),current_severity(db,row['id'])); snapshot.pop('actions');snapshot.pop('can_assign');snapshot.pop('can_set_follow_up');snapshot.pop('can_add_update');snapshot['follow_up'].pop('status');snapshot['follow_up'].pop('evaluated_at')
    db.execute('INSERT INTO synthetic_incident_events VALUES(?,?,?,?,?,?,?,?,?)',
               (row['id'], row['revision'], action, actor['id'], actor['email'], note, evidence,
                row['updated_at'], json.dumps(snapshot, sort_keys=True)))
    audit(db, actor['email'], 'synthetic_incident_' + action,
          json.dumps({'incident_id': row['id'], 'revision': row['revision'], 'scope': BOUNDARY['scope']}))


def install_routes(app, database, require_user, require_csrf, audit):
    @app.post('/api/incidents/from-observation')
    def from_observation(body: ObservationIncident, request: Request):
        current=require_user(request);require_csrf(request,current)
        digest=hashlib.sha256(json.dumps(body.model_dump(exclude={'request_key'}),sort_keys=True).encode()).hexdigest()
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,WRITE_ROLES)
            prior=db.execute('SELECT * FROM synthetic_incidents WHERE creator_id=? AND request_key=?',(actor['id'],body.request_key)).fetchone()
            if prior:
                if prior['creation_hash']!=digest or not observation_source(db,prior['id']):
                    raise HTTPException(409,'Creation key already has different contents; inspect saved incidents before starting another')
                return {**detail(db,prior,actor),'created':False}
            if db.execute('SELECT 1 FROM incident_observation_sources WHERE creator_id=? AND event_key=?',(actor['id'],body.event_key)).fetchone():
                raise HTTPException(409,'You already created an incident from this observation; open it in Alerts and add an investigation update')
            snapshot=capture_observation(db,body.event_key,body.content_hash)
            sample=snapshot['observation']
            if db.execute('SELECT count(*) FROM synthetic_incidents').fetchone()[0]>=MAX_INCIDENTS:
                raise HTTPException(409,'Local exercise capacity reached; no records are automatically deleted')
            identifier=secrets.token_hex(16);time=snapshot['captured_at'];evidence='Committed synthetic observation '+body.event_key
            db.execute('''INSERT INTO synthetic_incidents VALUES(?,?,?,?,?,?,?,?,?,'open',1,?,?,?)''',
                       (identifier,actor['id'],actor['email'],body.request_key,digest,sample['asset_id'],body.title,body.observation,body.severity,evidence,time,time))
            db.execute('INSERT INTO incident_observation_sources VALUES(?,?,?,?)',(identifier,body.event_key,actor['id'],json.dumps(snapshot,sort_keys=True)))
            row=visible(db,identifier,actor);event(db,row,actor,'create',body.observation,evidence,audit)
            audit(db,actor['email'],'synthetic_incident_observation_linked',json.dumps({'incident_id':identifier,'event_key':body.event_key}))
            return {**detail(db,row,actor),'created':True}

    @app.post('/api/incidents/{incident_id}/severity')
    def review_severity(incident_id: str, body: ReviewSeverity, request: Request):
        current=require_user(request);require_csrf(request,current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,WRITE_ROLES)
            row=visible(db,incident_id,actor)
            if row['revision']!=body.expected_revision or row['revision']>=MAX_REVISIONS or row['state']=='resolved':
                raise HTTPException(409,'Incident changed, is resolved or reached history capacity; reopen the current record')
            if current_severity(db,incident_id)==body.severity:raise HTTPException(409,'The selected severity is already current')
            now=datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO incident_triage VALUES(?,?,?) ON CONFLICT(incident_id) DO UPDATE SET severity=excluded.severity,updated_at=excluded.updated_at',(incident_id,body.severity,now))
            db.execute('UPDATE synthetic_incidents SET revision=revision+1,updated_at=? WHERE id=?',(now,incident_id))
            row=visible(db,incident_id,actor);event(db,row,actor,'severity_reviewed',body.note,'',audit)
            return detail(db,row,actor)

    @app.post('/api/incidents/{incident_id}/observations')
    def attach_observation(incident_id: str, body: AttachObservation, request: Request):
        current=require_user(request);require_csrf(request,current)
        digest=hashlib.sha256(json.dumps(body.model_dump(exclude={'request_key'}),sort_keys=True).encode()).hexdigest()
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,WRITE_ROLES)
            row=visible(db,incident_id,actor)
            prior=db.execute('SELECT request_hash,revision FROM incident_observation_attachments WHERE incident_id=? AND actor_id=? AND request_key=?',
                             (incident_id,actor['id'],body.request_key)).fetchone()
            if prior:
                if prior['request_hash']!=digest:raise HTTPException(409,'Attachment key already has different contents; inspect the current incident')
                return {**detail(db,row,actor),'created':False,'attachment_revision':prior['revision']}
            if row['revision']!=body.expected_revision or row['revision']>=MAX_REVISIONS or row['state']=='resolved':
                raise HTTPException(409,'Incident changed, is resolved or reached history capacity; reopen the current record')
            initial=observation_source(db,incident_id);attached=observation_attachments(db,incident_id)
            if len(attached)>=MAX_ATTACHED_OBSERVATIONS:raise HTTPException(409,'Saved-observation attachment capacity reached; existing evidence is retained')
            if (initial and initial['event_key']==body.event_key) or any(item['snapshot']['event_key']==body.event_key for item in attached):
                raise HTTPException(409,'This observation is already captured in the incident')
            snapshot=capture_observation(db,body.event_key,body.content_hash)
            if snapshot['observation']['asset_id']!=row['asset_id']:raise HTTPException(422,'Observation asset must exactly match the incident asset')
            context=initial or (attached[0]['snapshot'] if attached else None)
            if context and context['observation']['site_id']!=snapshot['observation']['site_id']:
                raise HTTPException(422,'Observation site must match the incident captured context')
            db.execute('UPDATE synthetic_incidents SET revision=revision+1,updated_at=? WHERE id=?',(snapshot['captured_at'],incident_id))
            row=visible(db,incident_id,actor)
            event(db,row,actor,'observation_attached',body.note,'Committed synthetic observation '+body.event_key,audit)
            db.execute('INSERT INTO incident_observation_attachments VALUES(?,?,?,?,?,?,?)',
                       (incident_id,body.event_key,row['revision'],actor['id'],body.request_key,digest,json.dumps(snapshot,sort_keys=True)))
            return {**detail(db,row,actor),'created':True,'attachment_revision':row['revision']}

    @app.post('/api/incidents/{incident_id}/investigation')
    def investigate(incident_id: str, body: InvestigationUpdate, request: Request):
        current=require_user(request);require_csrf(request,current)
        if body.kind=='evidence' and not body.evidence_refs:
            raise HTTPException(422,'Evidence updates require a reference; reference text is not independently verified')
        digest=hashlib.sha256(json.dumps(body.model_dump(exclude={'request_key'}),sort_keys=True).encode()).hexdigest()
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,WRITE_ROLES)
            row=visible(db,incident_id,actor)
            prior=db.execute('SELECT request_hash,revision FROM incident_investigation_keys WHERE incident_id=? AND actor_id=? AND request_key=?',
                             (incident_id,actor['id'],body.request_key)).fetchone()
            if prior:
                if prior['request_hash']!=digest:raise HTTPException(409,'This update key was already used with different contents; reopen the incident before adding a new update')
                return {**detail(db,row,actor),'created':False,'update_revision':prior['revision']}
            if row['revision']!=body.expected_revision or row['revision']>=MAX_REVISIONS or row['state']=='resolved':
                raise HTTPException(409,'Incident changed, is resolved or reached history capacity; reopen the current record')
            now=datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE synthetic_incidents SET revision=revision+1,updated_at=? WHERE id=?',(now,incident_id))
            row=visible(db,incident_id,actor)
            event(db,row,actor,'investigation_'+body.kind,body.note,body.evidence_refs,audit)
            db.execute('INSERT INTO incident_investigation_keys VALUES(?,?,?,?,?)',
                       (incident_id,actor['id'],body.request_key,digest,row['revision']))
            return {**detail(db,row,actor),'created':True,'update_revision':row['revision']}

    @app.post('/api/incidents/{incident_id}/follow-up')
    def set_followup(incident_id: str, body: FollowUp, request: Request):
        current=require_user(request);require_csrf(request,current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,WRITE_ROLES)
            row=visible(db,incident_id,actor)
            if row['revision']!=body.expected_revision or row['revision']>=MAX_REVISIONS or row['state']=='resolved':
                raise HTTPException(409,'Incident changed, is resolved or reached history capacity; reopen the current record')
            if followup(db,row)['due_at']==body.due_at:raise HTTPException(409,'The requested follow-up date is already current')
            now=datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO incident_followups VALUES(?,?,?) ON CONFLICT(incident_id) DO UPDATE SET due_at=excluded.due_at,updated_at=excluded.updated_at',(incident_id,body.due_at,now))
            db.execute('UPDATE synthetic_incidents SET revision=revision+1,updated_at=? WHERE id=?',(now,incident_id))
            row=visible(db,incident_id,actor);event(db,row,actor,'follow_up_changed',body.note,'',audit)
            return detail(db,row,actor)

    @app.get('/api/incidents/{incident_id}/assignment-candidates')
    def candidates(incident_id: str, request: Request):
        actor=require_user(request)
        with database() as db:
            db.execute('BEGIN');row=visible(db,incident_id,actor)
            if not controls_assignment(row,actor):raise HTTPException(403,'Only the creator or an administrator can choose incident ownership')
            if row['state']=='resolved' or row['revision']>=MAX_REVISIONS:raise HTTPException(409,'Assignment is unavailable for the current incident state or history limit')
            rows=db.execute("SELECT id,email,role FROM users WHERE disabled=0 AND role IN ('admin','operator') ORDER BY email LIMIT 100").fetchall()
        return {'candidates':[dict(row) for row in rows],**BOUNDARY}

    @app.post('/api/incidents/{incident_id}/assignment')
    def assign(incident_id: str, body: AssignIncident, request: Request):
        current=require_user(request);require_csrf(request,current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,WRITE_ROLES)
            row=visible(db,incident_id,actor)
            if not controls_assignment(row,actor):raise HTTPException(403,'Only the creator or an administrator can change incident ownership')
            if row['revision']!=body.expected_revision or row['revision']>=MAX_REVISIONS or row['state']=='resolved':
                raise HTTPException(409,'Incident changed, is resolved or reached history capacity; reopen the current record')
            target=None
            if body.assignee_id is not None:
                target=db.execute("SELECT id,email FROM users WHERE id=? AND disabled=0 AND role IN ('admin','operator')",(body.assignee_id,)).fetchone()
                if not target:raise HTTPException(422,'Choose an enabled Administrator or Operator account')
            prior=assignment(db,incident_id)
            if (prior['user_id'] if prior else None)==body.assignee_id:raise HTTPException(409,'The requested assignment is already current')
            now=datetime.now(timezone.utc).isoformat()
            db.execute('''INSERT INTO incident_assignments VALUES(?,?,?,?) ON CONFLICT(incident_id)
                DO UPDATE SET assignee_id=excluded.assignee_id,assignee_email=excluded.assignee_email,updated_at=excluded.updated_at''',
                (incident_id,body.assignee_id,target['email'] if target else None,now))
            db.execute('UPDATE synthetic_incidents SET revision=revision+1,updated_at=? WHERE id=?',(now,incident_id))
            row=visible(db,incident_id,actor);event(db,row,actor,'assigned' if target else 'unassigned',body.note,'',audit)
            return detail(db,row,actor)

    @app.post('/api/incidents/{incident_id}/maintenance-plan')
    def prepare_plan(incident_id: str, body: LinkedPlan, request: Request):
        current = require_user(request); require_csrf(request, current)
        digest = hashlib.sha256(json.dumps(body.model_dump(), sort_keys=True).encode()).hexdigest()
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = fresh_actor(db, current); require_role(actor, WRITE_ROLES)
            incident = visible(db, incident_id, actor)
            existing = db.execute('SELECT * FROM incident_plan_links WHERE incident_id=? AND creator_id=?', (incident_id, actor['id'])).fetchone()
            if existing:
                if existing['request_hash'] != digest: raise HTTPException(409, 'A plan is already linked for this account; open and revise that plan instead')
                row = planning.visible_plan(db, existing['plan_id'], actor)
                return {**planning.detail(db, row, actor), 'created': False}
            if incident['revision'] != body.expected_revision: raise HTTPException(409, 'Incident changed; reopen its current revision before preparing a plan')
            if incident['state'] == 'resolved': raise HTTPException(409, 'Reopen the incident exercise before preparing a new plan')
            if db.execute('SELECT count(*) FROM incident_plan_links WHERE incident_id=?', (incident_id,)).fetchone()[0] >= MAX_LINKS_PER_INCIDENT:
                raise HTTPException(409, 'Linked-plan capacity reached; existing records remain retained')
            fields = planning.PlanFields(asset_id=incident['asset_id'], title=('Inspect: ' + incident['title'])[:120],
                observation=incident['observation'], proposal=body.proposal,
                evidence_refs='Synthetic incident ' + incident_id + ' revision ' + str(incident['revision']),
                priority={'info': 'low', 'watch': 'medium', 'critical': 'critical'}[current_severity(db,incident_id)]).model_dump()
            key = hashlib.sha256(('incident-plan:' + incident_id).encode()).hexdigest()[:32]
            if db.execute('SELECT 1 FROM maintenance_requests WHERE creator_id=? AND request_key=?', (actor['id'], key)).fetchone():
                raise HTTPException(409, 'The linked-plan save key is already in use; no existing plan was attached or changed')
            identifier = secrets.token_hex(16); now = datetime.now(timezone.utc).isoformat()
            creation_hash = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
            db.execute('''INSERT INTO maintenance_requests(id,creator_id,creator_email,request_key,creation_hash,
                asset_id,title,observation,proposal,evidence_refs,priority,status,revision,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,'draft',1,?,?)''',
                (identifier, actor['id'], actor['email'], key, creation_hash, fields['asset_id'], fields['title'],
                 fields['observation'], fields['proposal'], fields['evidence_refs'], fields['priority'], now, now))
            snapshot = present(incident, actor, assignment(db,incident_id), followup(db,incident),current_severity(db,incident_id)); snapshot.pop('actions');snapshot.pop('can_assign');snapshot.pop('can_set_follow_up');snapshot.pop('can_add_update');snapshot['follow_up'].pop('status');snapshot['follow_up'].pop('evaluated_at')
            snapshot['source_observation']=observation_source(db,incident_id)
            snapshot['attached_observations']=observation_attachments(db,incident_id)
            db.execute('INSERT INTO incident_plan_links VALUES(?,?,?,?,?,?,?)',
                (identifier, incident_id, actor['id'], incident['revision'], digest, json.dumps(snapshot, sort_keys=True), now))
            row = planning.visible_plan(db, identifier, actor)
            planning.append_event(db, row, actor, 'created', 'Synthetic planning draft prepared from a frozen incident revision.', audit)
            audit(db, actor['email'], 'synthetic_incident_plan_linked', json.dumps({'incident_id': incident_id, 'incident_revision': incident['revision'], 'plan_id': identifier}))
            return {**planning.detail(db, row, actor), 'created': True}

    @app.get('/api/incidents')
    def list_incidents(request: Request, state: str = 'all', q: str = Query(default='', max_length=160),
                       offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=50),
                       ownership: Literal['all','assigned','created','unassigned'] = 'all',
                       follow_up: Literal['all','none','overdue','upcoming'] = 'all',
                       severity: Literal['all','info','watch','critical'] = 'all',
                       sort: Literal['updated','severity'] = 'updated'):
        actor = require_user(request); require_role(actor, READ_ROLES)
        if state not in ('all', 'active', *STATES): raise HTTPException(422, 'Unknown incident state')
        observed_at=datetime.now(timezone.utc)
        scope, args = ('(creator_id=? OR id IN (SELECT incident_id FROM incident_assignments WHERE assignee_id=?))', [actor['id'],actor['id']]) if actor['role'] == 'operator' else ('1=1', [])
        actor_scope, actor_args = scope, list(args)
        if ownership=='assigned':scope+=' AND id IN (SELECT incident_id FROM incident_assignments WHERE assignee_id=?)';args.append(actor['id'])
        elif ownership=='created':scope+=' AND creator_id=?';args.append(actor['id'])
        elif ownership=='unassigned':scope+=' AND id NOT IN (SELECT incident_id FROM incident_assignments WHERE assignee_id IS NOT NULL)'
        where, values = scope, list(args)
        if severity!='all':where+=' AND '+CURRENT_SEVERITY_SQL+'=?';values.append(severity)
        if follow_up=='none':
            where+=' AND id NOT IN (SELECT incident_id FROM incident_followups WHERE due_at IS NOT NULL)'
        elif follow_up in ('overdue','upcoming'):
            where+=" AND state!='resolved' AND id IN (SELECT incident_id FROM incident_followups WHERE due_at "+('<=' if follow_up=='overdue' else '>')+' ?)'
            values.append(observed_at.isoformat(timespec='microseconds'))
        if state == 'active': where += " AND state IN ('open','acknowledged')"
        elif state != 'all': where += ' AND state=?'; values.append(state)
        if q.strip():
            query = '%' + q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
            where += " AND (title LIKE ? ESCAPE '\\' OR asset_id LIKE ? ESCAPE '\\')"; values += [query, query]
        with database() as db:
            db.execute('BEGIN')
            # Aggregate the actor's complete active queue in this same read snapshot.
            # Filtered totals and ownership counts below retain their existing meaning.
            summary = db.execute("SELECT count(*) active, "
                "COALESCE(SUM(CASE WHEN " + CURRENT_SEVERITY_SQL + "='critical' THEN 1 ELSE 0 END),0) critical_active, "
                "COALESCE(SUM(CASE WHEN id IN (SELECT incident_id FROM incident_followups WHERE due_at<=?) THEN 1 ELSE 0 END),0) overdue_active, "
                "COALESCE(SUM(CASE WHEN id NOT IN (SELECT incident_id FROM incident_assignments WHERE assignee_id IS NOT NULL) THEN 1 ELSE 0 END),0) unassigned_active, "
                "COALESCE(SUM(CASE WHEN id IN (SELECT incident_id FROM incident_assignments WHERE assignee_id=?) THEN 1 ELSE 0 END),0) assigned_to_me_active "
                "FROM synthetic_incidents WHERE " + actor_scope + " AND state IN ('open','acknowledged')",
                [observed_at.isoformat(timespec='microseconds'), actor['id'], *actor_args]).fetchone()
            queue_summary = {**dict(summary), 'scope': 'all-accessible-saved-incidents',
                             'as_of': observed_at.isoformat(timespec='microseconds')}
            counts = {name: 0 for name in STATES}
            for row in db.execute('SELECT state,count(*) n FROM synthetic_incidents WHERE ' + scope + ' GROUP BY state', args): counts[row['state']] = row['n']
            total = db.execute('SELECT count(*) FROM synthetic_incidents WHERE ' + where, values).fetchone()[0]
            order=("CASE "+CURRENT_SEVERITY_SQL+" WHEN 'critical' THEN 0 WHEN 'watch' THEN 1 ELSE 2 END,") if sort=='severity' else ''
            rows = db.execute('SELECT * FROM synthetic_incidents WHERE ' + where + ' ORDER BY '+order+'updated_at DESC,id DESC LIMIT ? OFFSET ?', [*values, limit, offset]).fetchall()
            presented=[present(row, actor, assignment(db,row['id']), followup(db,row,observed_at),current_severity(db,row['id'])) for row in rows]
        return {'incidents': presented, 'counts': counts, 'queue_summary': queue_summary, 'total': total, 'severity_filter':severity,'sort':sort,
                'offset': offset, 'limit': limit, 'can_create': actor['role'] in WRITE_ROLES,
                'visibility': 'created by or assigned to you' if actor['role'] == 'operator' else 'all local records', **BOUNDARY}

    @app.get('/api/incidents/{incident_id}')
    def get_incident(incident_id: str, request: Request):
        actor = require_user(request)
        with database() as db:
            db.execute('BEGIN')
            return detail(db, visible(db, incident_id, actor), actor)

    @app.post('/api/incidents')
    def create_incident(body: CreateIncident, request: Request):
        current = require_user(request); require_csrf(request, current)
        payload = body.model_dump(exclude={'request_key'})
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = fresh_actor(db, current); require_role(actor, WRITE_ROLES)
            prior = db.execute('SELECT * FROM synthetic_incidents WHERE creator_id=? AND request_key=?', (actor['id'], body.request_key)).fetchone()
            if prior:
                if prior['creation_hash'] != digest: raise HTTPException(409, 'Save key conflicts with another incident; reload before creating a new exercise')
                return {**detail(db, prior, actor), 'created': False}
            if db.execute('SELECT count(*) FROM synthetic_incidents').fetchone()[0] >= MAX_INCIDENTS:
                raise HTTPException(409, 'Local exercise capacity reached; no records are automatically deleted')
            now = datetime.now(timezone.utc).isoformat(); identifier = secrets.token_hex(16)
            db.execute('''INSERT INTO synthetic_incidents VALUES(?,?,?,?,?,?,?,?,?,'open',1,?,?,?)''',
                       (identifier, actor['id'], actor['email'], body.request_key, digest, body.asset_id,
                        body.title, body.observation, body.severity, body.evidence_refs, now, now))
            row = visible(db, identifier, actor)
            event(db, row, actor, 'create', body.observation, body.evidence_refs, audit)
            return {**detail(db, row, actor), 'created': True}

    @app.post('/api/incidents/{incident_id}/actions')
    def act(incident_id: str, body: IncidentAction, request: Request):
        current = require_user(request); require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = fresh_actor(db, current); require_role(actor, WRITE_ROLES)
            row = visible(db, incident_id, actor)
            if row['revision'] != body.expected_revision: raise HTTPException(409, 'Incident changed; reload the current record before acting')
            if row['revision'] >= MAX_REVISIONS: raise HTTPException(409, 'Exercise history capacity reached; records remain retained')
            start, target = TRANSITIONS[body.action]
            if row['state'] != start: raise HTTPException(409, 'Action is not valid for the current incident state')
            if body.action == 'resolve' and not body.evidence_refs:
                raise HTTPException(422, 'Resolution requires a synthetic evidence reference; references are recorded, not independently verified')
            now = datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE synthetic_incidents SET state=?,revision=revision+1,updated_at=? WHERE id=?', (target, now, incident_id))
            row = visible(db, incident_id, actor)
            event(db, row, actor, body.action, body.note, body.evidence_refs, audit)
            return detail(db, row, actor)
