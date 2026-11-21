"""Bounded persisted synthetic history; receipt time is never observation freshness."""
import base64
from datetime import datetime,timezone
import json
import re

from fastapi import HTTPException,Query,Request
from acquisition_registry import DeliveryInput
from edge_delivery import identity
from maintenance_requests import require_role,READ_ROLES,WRITE_ROLES,ASSETS

CHANNELS={
    'acceleration_x_mps2':{'label':'Acceleration X','unit':'m/s²','sensor':'adxl345'},
    'acceleration_y_mps2':{'label':'Acceleration Y','unit':'m/s²','sensor':'adxl345'},
    'acceleration_z_mps2':{'label':'Acceleration Z','unit':'m/s²','sensor':'adxl345'},
    'motor_case_temperature_c':{'label':'Motor case temperature','unit':'°C','sensor':'ds18b20'},
    'bus_voltage_v':{'label':'Bus voltage','unit':'V','sensor':'ina219'},
    'current_a':{'label':'Current','unit':'A','sensor':'ina219'}}
BOUNDARY={'scope':'persisted-synthetic-observations','source_type':'synthetic','hardware_connected':False,
          'production_ready':False,'equipment_authorized':False,'model_deployed':False}


def decode_cursor(value):
    try:
        if len(value)>300 or not re.fullmatch(r'[A-Za-z0-9_-]+',value):raise ValueError()
        time,key=json.loads(base64.urlsafe_b64decode(value+'='*(-len(value)%4)))
        if not isinstance(time,str) or len(time)>40 or not re.fullmatch(r'[0-9a-f]{64}',key):raise ValueError()
        timestamp=datetime.fromisoformat(time)
        if timestamp.tzinfo is None:raise ValueError()
        return time,key
    except (ValueError,TypeError,KeyError):raise HTTPException(422,'Invalid history cursor')


def cursor(row):
    return base64.urlsafe_b64encode(json.dumps([row['committed_at'],row['event_key']],separators=(',',':')).encode()).decode().rstrip('=')


def present(row,now,max_age):
    try:
        envelope=DeliveryInput.model_validate_json(row['payload']).model_dump(mode='json')
        key,digest=identity(envelope)
        if key!=row['event_key'] or digest!=row['content_hash']:raise ValueError()
        sample=envelope['observation'];clock=sample['timestamp']
        if sample['device_id']!=row['device_id'] or envelope['binding_revision']!=row['binding_revision'] or not re.fullmatch(r'[0-9a-f]{32}',row['receipt_id']):raise ValueError()
        committed=datetime.fromisoformat(row['committed_at'])
        if committed.tzinfo is None:raise ValueError()
        observed=None;age=None;state='clock-unverified'
        if clock['clock_quality']=='device_clock_verified' and clock['device_time_utc'] is not None:
            observed=clock['device_time_utc'];age=(now-datetime.fromisoformat(observed)).total_seconds()
            state='future-time' if age<0 else 'stale' if age>max_age else 'within-display-age'
        return {'event_key':key,'content_hash':digest,'receipt_id':row['receipt_id'],
                'committed_at':row['committed_at'],'central_age_seconds':max(0,(now-committed).total_seconds()),
                'binding_revision':envelope['binding_revision'],'observation':sample,
                'freshness':{'state':state,'observed_at':observed,'observation_age_seconds':age,
                             'basis':'declared synthetic device clock only','max_age_seconds':max_age}}
    except (ValueError,TypeError,KeyError):
        raise HTTPException(503,'Stored observation failed integrity or contract checks; no history was returned')


def install_routes(app,database,require_user):
    @app.get('/api/acquisition/observations')
    def history(request:Request,device_id:str=Query(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_-]+$'),
                limit:int=Query(default=50,ge=1,le=100),before:str='',max_age_seconds:int=Query(default=60,ge=1,le=86400)):
        actor=require_user(request);require_role(actor,READ_ROLES)
        cutoff=decode_cursor(before) if before else None
        clause='device_id=?';params=[device_id]
        if cutoff:
            clause+=' AND (committed_at<? OR (committed_at=? AND event_key<?))';params.extend([cutoff[0],cutoff[0],cutoff[1]])
        with database() as db:
            db.execute('BEGIN')
            binding=db.execute('SELECT status,site_id,asset_id FROM acquisition_bindings WHERE device_id=?',(device_id,)).fetchone()
            if not binding:raise HTTPException(404,'Test binding not found')
            rows=db.execute('SELECT * FROM acquisition_observations WHERE '+clause+' ORDER BY committed_at DESC,event_key DESC LIMIT ?',(*params,limit+1)).fetchall()
        now=datetime.now(timezone.utc);selected=rows[:limit]
        records=[present(row,now,max_age_seconds) for row in selected]
        if any(record['observation']['site_id']!=binding['site_id'] or record['observation']['asset_id']!=binding['asset_id'] for record in records):
            raise HTTPException(503,'Stored observation does not match its immutable binding')
        return {**BOUNDARY,'can_prepare_incident':actor['role'] in WRITE_ROLES and binding['asset_id'] in ASSETS,
                'incident_asset_matches':binding['asset_id'] in ASSETS,'device_id':device_id,'site_id':binding['site_id'],'asset_id':binding['asset_id'],
                'binding_status':binding['status'],'as_of':now.isoformat(),'channels':CHANNELS,
                'max_age_seconds':max_age_seconds,'age_policy':'Operator display threshold; not an accepted operating target',
                'records':records,
                'next_before':cursor(selected[-1]) if len(rows)>limit else None,
                'order':'central commit descending; not source sampling order',
                'device_health':'not-established'}
