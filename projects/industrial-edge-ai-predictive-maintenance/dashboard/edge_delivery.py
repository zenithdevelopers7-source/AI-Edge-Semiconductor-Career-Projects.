"""Bounded SQLite synthetic delivery spool, independent of the web process.

No physical device credentials, broker acknowledgment or actuation is provided.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import base64
import hashlib
import json
import math
from pathlib import Path
import secrets
import sqlite3
import time
from acquisition_registry import DeliveryInput


HISTORY_STATES=('', 'pending', 'inflight', 'delivered', 'blocked')


class SpoolReadError(RuntimeError):
    """Required saved timing metadata is not safe to present as an outcome."""


def saved_time_utc(value):
    try:
        if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError()
        return datetime.fromtimestamp(value,timezone.utc).isoformat()
    except (ValueError,OverflowError,OSError):raise SpoolReadError('Unsupported saved queue timing') from None


def saved_timing(row):
    if row['state'] not in HISTORY_STATES[1:]:raise SpoolReadError('Unsupported saved queue state')
    return {'queued_at_utc':saved_time_utc(row['created_at']),
            'updated_at_utc':saved_time_utc(row['updated_at']),
            'retry_not_before_utc':saved_time_utc(row['next_at']) if row['state']=='pending' else None,
            'lease_expires_at_utc':saved_time_utc(row['lease_until']) if row['state']=='inflight' else None}


def history_cursor(created_at,event_key,state=''):
    value=json.dumps([2,created_at,event_key,state] if state else [1,created_at,event_key],separators=(',',':'),allow_nan=False)
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip('=')


def history_position(before,state=''):
    if not isinstance(before,str) or len(before)>256:raise ValueError('Invalid delivery history cursor')
    if not before:return None
    try:
        if any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in before):raise ValueError()
        value=json.loads(base64.b64decode(before+'='*(-len(before)%4),altchars=b'-_',validate=True))
        if not isinstance(value,list) or not value or type(value[0]) is not int:raise ValueError()
        if value[0]==1:
            if len(value)!=3 or state:raise ValueError()
        elif value[0]==2:
            if len(value)!=4 or value[3] not in HISTORY_STATES[1:] or value[3]!=state:raise ValueError()
        else:raise ValueError()
        if (type(value[1]) not in (int,float) or not math.isfinite(value[1]) or value[1]<0
                or not isinstance(value[2],str) or len(value[2])!=64 or any(c not in '0123456789abcdef' for c in value[2])):raise ValueError()
        return value[1],value[2]
    except (ValueError,TypeError,OverflowError,UnicodeError):raise ValueError('Invalid delivery history cursor') from None


def identity(envelope):
    observation=envelope['observation']
    key=json.dumps([observation['device_id'],observation['boot_id'],observation['event_type'],observation['sequence']],separators=(',',':'))
    source=json.loads(json.dumps(envelope))
    # Per-arrival receipt time is not immutable measurement content.
    source['observation']['timestamp'].pop('gateway_received_utc',None)
    content=json.dumps(source,sort_keys=True,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(key.encode()).hexdigest(),hashlib.sha256(content.encode()).hexdigest()


class Spool:
    def __init__(self,path,max_rows=10000,max_bytes=32*1024*1024,lease_seconds=45):
        self.path=Path(path);self.max_rows=max_rows;self.max_bytes=max_bytes;self.lease_seconds=lease_seconds
        if min(max_rows,max_bytes,lease_seconds)<=0:raise ValueError('Positive spool limits required')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS delivery_spool(
                event_key TEXT PRIMARY KEY,content_hash TEXT NOT NULL,payload TEXT NOT NULL,
                state TEXT NOT NULL,attempts INTEGER NOT NULL,next_at REAL NOT NULL,
                lease_token TEXT,lease_until REAL,receipt TEXT,last_error TEXT,
                created_at REAL NOT NULL,updated_at REAL NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS delivery_due ON delivery_spool(state,next_at,lease_until)')
            db.execute('CREATE INDEX IF NOT EXISTS delivery_history ON delivery_spool(created_at DESC,event_key ASC)')
            db.execute('CREATE INDEX IF NOT EXISTS delivery_state_history ON delivery_spool(state,created_at DESC,event_key ASC)')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:yield db
        finally:db.close()

    def enqueue(self,envelope):
        envelope=DeliveryInput.model_validate(envelope).model_dump(mode="json")
        key,digest=identity(envelope);payload=json.dumps(envelope,sort_keys=True,separators=(',',':'),allow_nan=False)
        now=time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT * FROM delivery_spool WHERE event_key=?',(key,)).fetchone()
            if previous:
                if previous['content_hash']!=digest:raise ValueError('Source identity has conflicting content')
                return {'event_key':key,'content_hash':digest,'tier':'edge-committed','created':False}
            rows,size=db.execute('SELECT COUNT(*),COALESCE(SUM(length(CAST(payload AS BLOB))),0) FROM delivery_spool').fetchone()
            if rows>=self.max_rows or size+len(payload.encode())>self.max_bytes:
                raise OverflowError('Spool capacity reached; no observation was accepted')
            db.execute('INSERT INTO delivery_spool VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       (key,digest,payload,'pending',0,now,None,None,None,None,now,now))
        return {'event_key':key,'content_hash':digest,'tier':'edge-committed','created':True}

    def claim(self):
        now=time.time();token=secrets.token_hex(16)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM delivery_spool WHERE (state='pending' AND next_at<=?) OR (state='inflight' AND lease_until<=?) ORDER BY created_at,event_key LIMIT 1",(now,now)).fetchone()
            if not row:return None
            db.execute("UPDATE delivery_spool SET state='inflight',attempts=attempts+1,lease_token=?,lease_until=?,updated_at=? WHERE event_key=?",(token,now+self.lease_seconds,now,row['event_key']))
        return {'event_key':row['event_key'],'content_hash':row['content_hash'],'envelope':json.loads(row['payload']),'token':token,'attempt':row['attempts']+1}

    def finish(self,claim,receipt=None,error=None,permanent=False):
        now=time.time()
        if receipt is not None:
            if not isinstance(receipt,dict):raise ValueError('Invalid receipt object')
            if (receipt.get('tier')!='central-committed' or receipt.get('event_key')!=claim['event_key']
                    or receipt.get('content_hash')!=claim['content_hash'] or not receipt.get('receipt_id')):
                raise ValueError('Central receipt does not match the durable source event')
            state='delivered'
        else:state='blocked' if permanent or claim['attempt']>=8 else 'pending'
        with self.db() as db:
            changed=db.execute('''UPDATE delivery_spool SET state=?,next_at=?,lease_token=NULL,lease_until=NULL,
                receipt=?,last_error=?,updated_at=? WHERE event_key=? AND state='inflight' AND lease_token=?''',
                (state,now+min(300,2**min(claim['attempt'],8)),json.dumps(receipt,sort_keys=True) if receipt else None,
                 error,now,claim['event_key'],claim['token'])).rowcount
        return bool(changed)

    def attempt(self,sender):
        return self.process(self.claim(),sender)

    def process(self,claim,sender):
        if not claim:return {'attempted':False}
        try:
            status,result=sender(claim['envelope'])
            if status in (200,201):
                try:self.finish(claim,receipt=result)
                except ValueError:self.finish(claim,error='invalid-central-receipt',permanent=True)
            else:self.finish(claim,error='http-'+str(status),permanent=400<=status<500 and status not in (408,429))
        except Exception:
            # Do not persist exception strings that might contain credentials or payloads.
            self.finish(claim,error='transport-unavailable')
        return {'attempted':True,'event_key':claim['event_key']}

    def status(self,before='',limit=20,state=''):
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('Delivery history limit must be 1-100')
        if not isinstance(state,str) or state not in HISTORY_STATES:raise ValueError('Invalid delivery history state')
        position=history_position(before,state)
        with self.db() as db:
            db.execute('BEGIN')
            counts={state:0 for state in ('pending','inflight','delivered','blocked')}
            counts.update(dict(db.execute('SELECT state,COUNT(*) FROM delivery_spool GROUP BY state').fetchall()))
            usage=db.execute('SELECT COUNT(*) AS records,COALESCE(SUM(length(CAST(payload AS BLOB))),0) AS payload_bytes FROM delivery_spool').fetchone()
            clauses=[];params=[]
            if state:clauses.append('state=?');params.append(state)
            if position:clauses.append('(created_at<? OR (created_at=? AND event_key>?))');params.extend((position[0],position[0],position[1]))
            where=' WHERE '+' AND '.join(clauses) if clauses else ''
            params.append(limit+1)
            rows=db.execute('SELECT created_at,updated_at,next_at,lease_until,event_key,state,attempts,last_error,receipt FROM delivery_spool'+where+' ORDER BY created_at DESC,event_key ASC LIMIT ?',params).fetchall()
        page=rows[:limit]
        return {'counts':counts,'records':[{**{key:row[key] for key in ('event_key','state','attempts','last_error','receipt')},**saved_timing(row)} for row in page],
                'page':{'limit':limit,'before':before or None,'next_before':history_cursor(page[-1]['created_at'],page[-1]['event_key'],state) if len(rows)>limit else None,'order':'created-desc-event-asc','state':state},
                'limits':{'records':self.max_rows,'payload_bytes':self.max_bytes},
                'usage':dict(usage),
                'retention':'No automatic deletion; delivered identities count toward capacity.'}
