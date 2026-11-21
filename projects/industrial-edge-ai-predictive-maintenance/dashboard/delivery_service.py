"""Synthetic edge/central receipts. Local relay and HTTP worker share commit rules."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import secrets
from typing import Literal

from fastapi import HTTPException,Request,Response,Query
from acquisition_registry import DeliveryInput
from edge_delivery import Spool,SpoolReadError,identity
from maintenance_requests import fresh_actor,require_role,READ_ROLES

BOUNDARY={'scope':'local-synthetic-delivery','hardware_connected':False,'equipment_authorized':False,
          'production_ready':False,'broker_receipt':None,'model_deployed':False}



def init_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS acquisition_observations(
        event_key TEXT PRIMARY KEY,content_hash TEXT NOT NULL,device_id TEXT NOT NULL,
        binding_revision INTEGER NOT NULL,payload TEXT NOT NULL,receipt_id TEXT UNIQUE NOT NULL,
        committed_at TEXT NOT NULL,actor TEXT NOT NULL,
        FOREIGN KEY(device_id) REFERENCES acquisition_bindings(device_id))''')

    db.execute('CREATE INDEX IF NOT EXISTS acquisition_history ON acquisition_observations(device_id,committed_at DESC,event_key DESC)')


def matching_binding(db,body):
    obs=body.observation
    row=db.execute('SELECT * FROM acquisition_bindings WHERE device_id=?',(obs.device_id,)).fetchone()
    if (not row or row['status']!='active' or row['revision']!=body.binding_revision
            or row['site_id']!=obs.site_id or row['asset_id']!=obs.asset_id):
        raise HTTPException(403,'No active exact synthetic binding at this revision')


def commit_observation(database,audit,current,body):
    envelope=body.model_dump(mode='json');key,digest=identity(envelope);conflict=False
    with database() as db:
        db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,('admin','operator'))
        matching_binding(db,body)
        previous=db.execute('SELECT * FROM acquisition_observations WHERE event_key=?',(key,)).fetchone()
        if previous and previous['content_hash']!=digest:
            audit(db,actor['email'],'synthetic_ingest_conflict',key);conflict=True
        elif previous:row=previous;created=False
        else:
            if db.execute('SELECT COUNT(*) FROM acquisition_observations').fetchone()[0]>=10000:
                raise HTTPException(429,'Local observation capacity reached')
            now=datetime.now(timezone.utc).isoformat();receipt=secrets.token_hex(16)
            db.execute('INSERT INTO acquisition_observations VALUES(?,?,?,?,?,?,?,?)',
                       (key,digest,body.observation.device_id,body.binding_revision,json.dumps(envelope,sort_keys=True),receipt,now,actor['email']))
            audit(db,actor['email'],'synthetic_central_commit',key)
            row=db.execute('SELECT * FROM acquisition_observations WHERE event_key=?',(key,)).fetchone();created=True
    if conflict:raise HTTPException(409,'Same source identity has different content; original preserved')
    return created,{**BOUNDARY,'tier':'central-committed','event_key':key,'content_hash':digest,
                    'receipt_id':row['receipt_id'],'committed_at':row['committed_at']}


def install_routes(app,database,require_user,require_csrf,audit,default_spool_path):
    def spool():return Spool(Path(os.environ.get('EDGEOPS_DELIVERY_SPOOL_DB',str(default_spool_path))))

    @app.post('/api/acquisition/ingest')
    def ingest(body:DeliveryInput,request:Request,response:Response):
        current=require_user(request);require_csrf(request,current)
        created,receipt=commit_observation(database,audit,current,body)
        response.status_code=201 if created else 200
        return receipt

    @app.post('/api/acquisition/queue')
    def queue(body:DeliveryInput,request:Request,response:Response):
        current=require_user(request);require_csrf(request,current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,('admin','operator'));matching_binding(db,body)
            try:receipt=spool().enqueue(body.model_dump(mode='json'))
            except OverflowError as error:raise HTTPException(429,str(error))
            except ValueError as error:raise HTTPException(409,str(error))
            audit(db,actor['email'],'synthetic_edge_queue',receipt['event_key'])
        response.status_code=201 if receipt['created'] else 200
        return {**BOUNDARY,**receipt,'central_committed':False}

    @app.get('/api/acquisition/delivery')
    def delivery_status(request:Request,before:str=Query(default='',max_length=256),limit:int=Query(default=20,ge=1,le=100),state:Literal['','pending','inflight','delivered','blocked']=''):
        require_role(require_user(request),READ_ROLES)
        try:result=spool().status(before=before,limit=limit,state=state)
        except ValueError:raise HTTPException(422,'Invalid delivery history cursor or limit') from None
        except SpoolReadError:raise HTTPException(503,'Saved delivery timing is unavailable or inconsistent') from None
        with database() as db:central=db.execute('SELECT COUNT(*) FROM acquisition_observations').fetchone()[0]
        return {**BOUNDARY,**result,'central_records':central,'relay_mode':'local in-process test relay; HTTP worker available separately'}

    @app.post('/api/acquisition/deliver-once')
    def deliver_once(request:Request):
        current=require_user(request);require_csrf(request,current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE');actor=fresh_actor(db,current);require_role(actor,('admin','operator'))
            local_spool=spool();claim=local_spool.claim()
            if claim:audit(db,actor['email'],'synthetic_local_delivery_attempt',claim['event_key'])
        def send(envelope):
            try:
                created,receipt=commit_observation(database,audit,current,DeliveryInput.model_validate(envelope))
                return (201 if created else 200),receipt
            except HTTPException as error:return error.status_code,{}
        result=local_spool.process(claim,send)
        return {**BOUNDARY,**result,'relay_mode':'local-in-process; not a network or hardware test'}
