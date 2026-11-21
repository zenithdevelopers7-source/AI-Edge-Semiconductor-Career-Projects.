"""Evidence register, not automatic production or physical-safety certification."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from hardware_catalog import HARDWARE
from maintenance_requests import fresh_actor, require_role, READ_ROLES

CATALOG = json.loads((Path(__file__).parent/'readiness_catalog.json').read_text(encoding='utf-8'))
DEFINITIONS = {item['id']: item for item in CATALOG['items']}
assert len(DEFINITIONS) == 53
assert {kind:sum(item['kind']==kind for item in DEFINITIONS.values()) for kind in ('requirement','demonstration','target')} == {'requirement':18,'demonstration':15,'target':20}
CATALOG_HASH = hashlib.sha256(json.dumps(CATALOG, sort_keys=True).encode()).hexdigest()
BOUNDARY = {'scope': 'readiness-tracking-only', 'production_ready': False,
            'physical_acceptance_verified': False, 'equipment_authorized': False}
SCOPE_FIELDS = {
    'release_version':'Exact release version', 'site':'Deployment site',
    'equipment':'Physical equipment and asset scope', 'features':'Supported features',
    'operating_conditions':'Accepted operating conditions', 'exclusions':'Explicit exclusions (write None if none)',
    'support_owner':'Support and escalation owner', 'residual_risks':'Residual risks and limitations',
    'blocking_defects':'Blocking safety/security defects (unknown, open, or none)',
    'hardware_review_ref':'Qualified engineering / physical-safety acceptance reference',
    'security_review_ref':'Security acceptance reference', 'operations_review_ref':'Operations acceptance / training / handover reference',
    'final_acceptance_ref':'Dated final acceptance record and named reviewers'}
BOUND_SCOPE = tuple(key for key in SCOPE_FIELDS if not key.endswith('_ref'))


class RecordInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0, strict=True)
    status: Literal['not_started','in_progress','blocked','evidence_ready']
    owner: str = Field(default='',max_length=200)
    evidence: str = Field(default='',max_length=2000)
    notes: str = Field(default='',max_length=1500)
    target_value: str = Field(default='',max_length=400)

    @field_validator('owner','evidence','notes','target_value')
    @classmethod
    def trimmed(cls,value):return value.strip()


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1,strict=True)
    expected_scope_revision: int = Field(ge=0,strict=True)
    decision: Literal['accepted','rejected']
    note: str = Field(min_length=10,max_length=1000)
    qualification_reference: str = Field(min_length=10,max_length=600)

    @field_validator('note','qualification_reference')
    @classmethod
    def substantive(cls,value):
        if len(value.strip())<10:raise ValueError('Provide a substantive review and qualification/reference record')
        return value.strip()


class ScopeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=0,strict=True)
    values: dict[str,str]

    @field_validator('values')
    @classmethod
    def valid_fields(cls,value):
        if set(value)!=set(SCOPE_FIELDS):raise ValueError('Supply the complete known release-scope field set')
        if any(len(text)>500 for text in value.values()):raise ValueError('Scope fields must be at most 500 characters each')
        if value.get('blocking_defects','').strip().lower() not in ('','unknown','open','none'):raise ValueError('Blocking defects must be unknown, open, or none')
        return {key:text.strip() for key,text in value.items()}


def init_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS readiness_records(
        item_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,status TEXT NOT NULL,
        owner TEXT NOT NULL,evidence TEXT NOT NULL,notes TEXT NOT NULL,target_value TEXT NOT NULL,
        created_by_id INTEGER NOT NULL REFERENCES users(id),updated_by_id INTEGER NOT NULL REFERENCES users(id),
        updated_by TEXT NOT NULL,updated_at TEXT NOT NULL,reviewer TEXT,review_note TEXT,
        qualification_reference TEXT,reviewed_scope_revision INTEGER)''')
    db.execute('''CREATE TABLE IF NOT EXISTS readiness_events(
        item_id TEXT NOT NULL,revision INTEGER NOT NULL,action TEXT NOT NULL,actor TEXT NOT NULL,
        note TEXT NOT NULL,time_utc TEXT NOT NULL,snapshot_json TEXT NOT NULL,
        PRIMARY KEY(item_id,revision))''')
    db.execute('''CREATE TABLE IF NOT EXISTS readiness_release_scope(
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision INTEGER NOT NULL,
        binding_revision INTEGER NOT NULL,values_json TEXT NOT NULL,updated_by TEXT NOT NULL,updated_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS readiness_scope_events(
        revision INTEGER PRIMARY KEY,actor TEXT NOT NULL,time_utc TEXT NOT NULL,values_json TEXT NOT NULL)''')


def scope_record(db):
    row=db.execute('SELECT * FROM readiness_release_scope WHERE singleton=1').fetchone()
    return {'revision':row['revision'],'binding_revision':row['binding_revision'],'values':json.loads(row['values_json']),
            'updated_by':row['updated_by'],'updated_at':row['updated_at']} if row else {
        'revision':0,'binding_revision':0,'values':{key:'' for key in SCOPE_FIELDS},'updated_by':None,'updated_at':None}


def get_record(db,item_id):
    if item_id not in DEFINITIONS:raise HTTPException(404,'Readiness criterion not found')
    row=db.execute('SELECT * FROM readiness_records WHERE item_id=?',(item_id,)).fetchone()
    return dict(row) if row else {'item_id':item_id,'revision':0,'status':'not_started','owner':'','evidence':'','notes':'',
        'target_value':'','created_by_id':None,'updated_by_id':None,'updated_by':None,'updated_at':None,
        'reviewer':None,'review_note':None,'qualification_reference':None,'reviewed_scope_revision':None}


def presented(row,actor):
    result={key:value for key,value in row.items() if key not in ('created_by_id','updated_by_id')}
    result['actions']={'edit':actor['role']=='admin','review':actor['role']=='admin' and row['status']=='evidence_ready'
                      and actor['id'] not in (row['created_by_id'],row['updated_by_id'])}
    return result


def history(db,item_id):
    result=[]
    for event in db.execute('SELECT * FROM readiness_events WHERE item_id=? ORDER BY revision DESC',(item_id,)):
        record=dict(event);snapshot=json.loads(record.pop('snapshot_json'))
        for key in ('created_by_id','updated_by_id'):snapshot.pop(key,None)
        record['snapshot']=snapshot;result.append(record)
    return result


def append_event(db,row,actor,action,note,audit):
    db.execute('INSERT INTO readiness_events VALUES(?,?,?,?,?,?,?)',(row['item_id'],row['revision'],action,
        actor['email'],note,row['updated_at'],json.dumps(row,sort_keys=True)))
    audit(db,actor['email'],'readiness_'+action,json.dumps({'item_id':row['item_id'],'revision':row['revision'],'scope':'tracking-only'}))


def summary(db,actor):
    records=[presented(get_record(db,item_id),actor) for item_id in DEFINITIONS]
    scope=scope_record(db);accepted=sum(record['status']=='accepted' for record in records)
    missing=[key for key,value in scope['values'].items() if not value]
    return {'catalog':CATALOG,'catalog_sha256':CATALOG_HASH,'records':records,'release':scope,
        'scope_fields':SCOPE_FIELDS,'can_edit':actor['role']=='admin','total':53,'accepted':accepted,
        'missing_scope_fields':missing,'blocking_defects_clear':scope['values']['blocking_defects'].lower()=='none',
        'tracking_complete':accepted==53 and not missing and scope['values']['blocking_defects'].lower()=='none',
        'current_user':actor['email'],**BOUNDARY}


def install_routes(app,database,require_user,require_csrf,record_audit):
    def reader(request):
        actor=require_user(request);require_role(actor,READ_ROLES);return actor

    @app.get('/api/production-readiness')
    def register(request:Request):
        actor=reader(request)
        with database() as db:
            db.execute('BEGIN');return summary(db,actor)

    @app.get('/api/production-readiness/export')
    def export(request:Request):
        actor=reader(request)
        with database() as db:
            db.execute('BEGIN');result=summary(db,actor)
            result['histories']={item_id:history(db,item_id) for item_id in DEFINITIONS}
            result['scope_history']=[dict(row) for row in db.execute('SELECT revision,actor,time_utc,values_json FROM readiness_scope_events ORDER BY revision DESC')]
        result['hardware']=[dict(id=i,name=n,purpose=p,category=c,lifecycle='planned',physical_inventory_verified=False) for i,n,p,c in HARDWARE]
        result['exported_at']=datetime.now(timezone.utc).isoformat();return result

    @app.get('/api/production-readiness/items/{item_id}')
    def item(item_id:str,request:Request):
        actor=reader(request)
        with database() as db:
            db.execute('BEGIN');return {'definition':DEFINITIONS.get(item_id),'record':presented(get_record(db,item_id),actor),
                'history':history(db,item_id),'release':scope_record(db),**BOUNDARY}

    @app.put('/api/production-readiness/items/{item_id}')
    def update(item_id:str,body:RecordInput,request:Request):
        current=require_user(request);require_csrf(request,current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,('admin',))
            previous=get_record(db,item_id)
            if previous['revision']!=body.expected_revision:raise HTTPException(409,'Criterion changed; reload before saving')
            if body.status=='evidence_ready':
                if len(body.owner)<3 or len(body.evidence)<10:raise HTTPException(422,'Assign an owner and provide substantive evidence references before review')
                if DEFINITIONS[item_id]['kind']=='target' and not any(char.isdigit() for char in body.target_value):raise HTTPException(422,'Specify an agreed measurable target with a numeric value and units/context')
            now=datetime.now(timezone.utc).isoformat()
            db.execute('''INSERT INTO readiness_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(item_id) DO UPDATE SET revision=excluded.revision,status=excluded.status,
                owner=excluded.owner,evidence=excluded.evidence,notes=excluded.notes,target_value=excluded.target_value,
                updated_by_id=excluded.updated_by_id,updated_by=excluded.updated_by,updated_at=excluded.updated_at,
                reviewer=NULL,review_note=NULL,qualification_reference=NULL,reviewed_scope_revision=NULL''',
                (item_id,previous['revision']+1,body.status,body.owner,body.evidence,body.notes,body.target_value,
                 previous['created_by_id'] or actor['id'],actor['id'],actor['email'],now,None,None,None,None))
            row=get_record(db,item_id);append_event(db,row,actor,'edited','Evidence record edited; any previous acceptance is invalid for this revision.',record_audit)
            return {'definition':DEFINITIONS[item_id],'record':presented(row,actor),'history':history(db,item_id),'release':scope_record(db),**BOUNDARY}

    @app.post('/api/production-readiness/items/{item_id}/review')
    def review(item_id:str,body:ReviewInput,request:Request):
        current=require_user(request);require_csrf(request,current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,('admin',))
            row=get_record(db,item_id);scope=scope_record(db)
            if row['revision']!=body.expected_revision or scope['binding_revision']!=body.expected_scope_revision:raise HTTPException(409,'Criterion or release scope changed; reload before reviewing')
            if actor['id'] in (row['created_by_id'],row['updated_by_id']):raise HTTPException(403,'Independent account required; creators/editors cannot accept their own evidence')
            if row['status']!='evidence_ready':raise HTTPException(409,'Submit evidence before recording a review')
            if not all(scope['values'][key] for key in ('release_version','site','equipment','features','operating_conditions')):raise HTTPException(409,'Define the release, site, equipment, features and operating conditions before acceptance review')
            db.execute('''UPDATE readiness_records SET revision=revision+1,status=?,reviewer=?,review_note=?,
                qualification_reference=?,reviewed_scope_revision=?,updated_at=? WHERE item_id=?''',
                (body.decision,actor['email'],body.note,body.qualification_reference,scope['binding_revision'],datetime.now(timezone.utc).isoformat(),item_id))
            row=get_record(db,item_id);append_event(db,row,actor,body.decision,body.note,record_audit)
            return {'definition':DEFINITIONS[item_id],'record':presented(row,actor),'history':history(db,item_id),'release':scope,**BOUNDARY}

    @app.put('/api/production-readiness/release-scope')
    def update_scope(body:ScopeInput,request:Request):
        current=require_user(request);require_csrf(request,current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,('admin',))
            previous=scope_record(db)
            if previous['revision']!=body.expected_revision:raise HTTPException(409,'Release scope changed; reload before saving')
            if previous['values']==body.values:return summary(db,actor)
            changed=any(previous['values'][key]!=body.values[key] for key in BOUND_SCOPE)
            revision=previous['revision']+1;binding=previous['binding_revision']+int(changed);now=datetime.now(timezone.utc).isoformat();encoded=json.dumps(body.values,sort_keys=True)
            db.execute('''INSERT INTO readiness_release_scope VALUES(1,?,?,?,?,?) ON CONFLICT(singleton) DO UPDATE SET
                revision=excluded.revision,binding_revision=excluded.binding_revision,values_json=excluded.values_json,
                updated_by=excluded.updated_by,updated_at=excluded.updated_at''',(revision,binding,encoded,actor['email'],now))
            db.execute('INSERT INTO readiness_scope_events VALUES(?,?,?,?)',(revision,actor['email'],now,encoded))
            if changed:
                accepted=db.execute("SELECT item_id FROM readiness_records WHERE status IN ('accepted','evidence_ready')").fetchall()
                for item_row in accepted:
                    item_id=item_row['item_id'];db.execute("UPDATE readiness_records SET status='in_progress',revision=revision+1,reviewer=NULL,review_note=NULL,qualification_reference=NULL,reviewed_scope_revision=NULL,updated_at=? WHERE item_id=?",(now,item_id))
                    append_event(db,get_record(db,item_id),actor,'scope_changed','Bound release scope changed; previous acceptance requires fresh review.',record_audit)
            record_audit(db,actor['email'],'readiness_scope_updated',json.dumps({'revision':revision,'binding_revision':binding}))
            return summary(db,actor)
