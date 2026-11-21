"""Synthetic acquisition bindings and V2 preflight; no device enrollment or ingest."""
from datetime import datetime, timezone
import json
from typing import Annotated, Literal

from fastapi import HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from maintenance_requests import fresh_actor, require_role, READ_ROLES

Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=64, pattern=r'^[A-Za-z0-9_-]+$')]
Counter = Annotated[int, Field(strict=True, ge=0, le=4294967295)]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-1e12, le=1e12)]
BOUNDARY = {'scope': 'synthetic-acquisition-preflight', 'production_ready': False,
            'hardware_connected': False, 'equipment_authorized': False,
            'observation_persisted': False, 'device_credential_issued': False}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Binding(StrictModel):
    site_id: Identifier
    asset_id: Identifier
    device_id: Identifier
    source_type: Literal['synthetic']
    transport: Literal['simulator']
    firmware_ref: str = Field(min_length=1, max_length=120, strict=True)
    configuration_sha256: str = Field(pattern=r'^[0-9a-f]{64}$', strict=True)

    @field_validator('firmware_ref')
    @classmethod
    def substantive(cls, value):
        if not value.strip():
            raise ValueError('A simulator configuration reference is required')
        return value.strip()


class Revision(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)


class SampleTime(StrictModel):
    device_uptime_ms: Counter
    device_time_utc: datetime | None
    gateway_received_utc: datetime
    clock_quality: Literal['gateway_receipt_only', 'device_clock_verified', 'clock_unverified']

    @field_validator('device_time_utc', 'gateway_received_utc', mode='before')
    @classmethod
    def timestamp_string(cls, value):
        if value is not None and (not isinstance(value, str) or len(value) > 40 or 'T' not in value):
            raise ValueError('Use an explicit timezone-aware timestamp string')
        return value

    @field_validator('device_time_utc', 'gateway_received_utc')
    @classmethod
    def timezone_required(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('Timestamp timezone is required')
        return value.astimezone(timezone.utc) if value is not None else None

    @model_validator(mode='after')
    def clock_consistency(self):
        if self.clock_quality == 'device_clock_verified' and self.device_time_utc is None:
            raise ValueError('Verified device clock requires device time')
        return self


class Measurements(StrictModel):
    acceleration_x_mps2: Number | None
    acceleration_y_mps2: Number | None
    acceleration_z_mps2: Number | None
    motor_case_temperature_c: Number | None
    bus_voltage_v: Number | None
    current_a: Number | None


SensorQuality = Literal['valid', 'invalid', 'not_connected', 'stale']


class Quality(StrictModel):
    adxl345: SensorQuality
    ds18b20: SensorQuality
    ina219: SensorQuality
    calibration: Literal['verified', 'not_verified', 'expired', 'unknown']
    session_quality: Literal['verified', 'inferred', 'unavailable']


class Observation(StrictModel):
    schema_version: Literal['2.0']
    event_type: Literal['telemetry.sample']
    source_type: Literal['synthetic']
    site_id: Identifier
    asset_id: Identifier
    device_id: Identifier
    boot_id: Identifier | None
    sequence: Counter
    timestamp: SampleTime
    measurements: Measurements
    quality: Quality

    @model_validator(mode='after')
    def consistent_quality(self):
        m, q = self.measurements, self.quality
        groups = [(q.adxl345, [m.acceleration_x_mps2, m.acceleration_y_mps2, m.acceleration_z_mps2]),
                  (q.ds18b20, [m.motor_case_temperature_c]), (q.ina219, [m.bus_voltage_v, m.current_a])]
        for quality, values in groups:
            if quality == 'valid' and any(value is None for value in values):
                raise ValueError('Valid channels require numeric readings; zero is valid')
            if quality != 'valid' and any(value is not None for value in values):
                raise ValueError('Invalid, missing or stale channels must be null')
        if q.session_quality == 'verified' and self.boot_id is None:
            raise ValueError('Verified session requires a boot identifier')
        if q.session_quality == 'unavailable' and self.boot_id is not None:
            raise ValueError('Unavailable session must not invent boot identity')
        return self



class DeliveryInput(StrictModel):
    binding_revision:int=Field(strict=True,ge=1)
    observation:Observation

    @model_validator(mode='after')
    def verified_synthetic_session(self):
        if self.observation.boot_id is None or self.observation.quality.session_quality!='verified':
            raise ValueError('Delivery needs an explicit synthetic boot/session identity; preflight-only ambiguous sessions cannot be deduplicated')
        return self


def init_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS acquisition_bindings(
        device_id TEXT PRIMARY KEY, site_id TEXT NOT NULL, asset_id TEXT NOT NULL,
        definition TEXT NOT NULL, revision INTEGER NOT NULL, status TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        created_by INTEGER NOT NULL REFERENCES users(id))''')
    db.execute('''CREATE TABLE IF NOT EXISTS acquisition_binding_events(
        device_id TEXT NOT NULL REFERENCES acquisition_bindings(device_id), revision INTEGER NOT NULL,
        action TEXT NOT NULL, actor TEXT NOT NULL, time_utc TEXT NOT NULL,
        PRIMARY KEY(device_id,revision))''')


def view(row):
    return {**json.loads(row['definition']), 'revision': row['revision'],
            'status': row['status'], 'created_at': row['created_at'], 'updated_at': row['updated_at']}


def install_routes(app, database, require_user, require_csrf, audit):
    @app.get('/api/acquisition-bindings')
    def list_bindings(request: Request, after: str = '', limit: int = Query(default=50, ge=1, le=100)):
        require_role(require_user(request), READ_ROLES)
        if len(after) > 64:
            raise HTTPException(422, 'Invalid cursor')
        with database() as db:
            rows = db.execute('SELECT * FROM acquisition_bindings WHERE device_id>? ORDER BY device_id LIMIT ?',
                              (after, limit + 1)).fetchall()
        return {**BOUNDARY, 'bindings': [view(row) for row in rows[:limit]],
                'next_after': rows[limit-1]['device_id'] if len(rows) > limit else None}

    @app.get('/api/acquisition-contract')
    def contract(request: Request):
        require_role(require_user(request), READ_ROLES)
        return {**BOUNDARY, 'profile': 'edgeops-local-synthetic-v2-preflight-v1',
                'schema': Observation.model_json_schema(),
                'note': 'Stricter synthetic-only profile; original EA-22 candidate is unchanged. No receipt or ingestion.'}

    @app.post('/api/acquisition-bindings')
    def create_binding(body: Binding, request: Request, response: Response):
        current = require_user(request)
        require_csrf(request, current)
        definition = json.dumps(body.model_dump(), sort_keys=True, separators=(',', ':'))
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = fresh_actor(db, current)
            require_role(actor, ('admin',))
            previous = db.execute('SELECT * FROM acquisition_bindings WHERE device_id=?', (body.device_id,)).fetchone()
            if previous:
                if previous['definition'] != definition or previous['status'] != 'active':
                    raise HTTPException(409, 'Device ID already has a different or retired binding; use a new test identity')
                result, created = view(previous), False
            else:
                now = datetime.now(timezone.utc).isoformat()
                db.execute('INSERT INTO acquisition_bindings VALUES(?,?,?,?,?,?,?,?,?)',
                           (body.device_id, body.site_id, body.asset_id, definition, 1, 'active', now, now, actor['id']))
                db.execute('INSERT INTO acquisition_binding_events VALUES(?,?,?,?,?)',
                           (body.device_id, 1, 'created', actor['email'], now))
                audit(db, actor['email'], 'synthetic_binding_created', body.device_id)
                result = view(db.execute('SELECT * FROM acquisition_bindings WHERE device_id=?', (body.device_id,)).fetchone())
                created = True
        response.status_code = 201 if created else 200
        return {**BOUNDARY, 'binding': result, 'created': created}

    @app.post('/api/acquisition-bindings/{device_id}/retire')
    def retire_binding(device_id: str, body: Revision, request: Request):
        current = require_user(request)
        require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = fresh_actor(db, current)
            require_role(actor, ('admin',))
            row = db.execute('SELECT * FROM acquisition_bindings WHERE device_id=?', (device_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Test binding not found')
            if row['revision'] != body.expected_revision or row['status'] != 'active':
                raise HTTPException(409, 'Binding changed or was retired; refresh')
            now = datetime.now(timezone.utc).isoformat()
            db.execute("UPDATE acquisition_bindings SET status='retired',revision=revision+1,updated_at=? WHERE device_id=?", (now, device_id))
            db.execute('INSERT INTO acquisition_binding_events VALUES(?,?,?,?,?)',
                       (device_id, row['revision']+1, 'retired', actor['email'], now))
            audit(db, actor['email'], 'synthetic_binding_retired', device_id)
        return {**BOUNDARY, 'retired': True}

    @app.post('/api/acquisition/validate')
    def validate_observation(body: Observation, request: Request):
        current = require_user(request)
        require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = fresh_actor(db, current)
            require_role(actor, ('admin', 'operator'))
            row = db.execute('SELECT * FROM acquisition_bindings WHERE device_id=?', (body.device_id,)).fetchone()
            if not row or row['status'] != 'active' or row['site_id'] != body.site_id or row['asset_id'] != body.asset_id:
                raise HTTPException(403, 'Observation does not match an active synthetic binding')
        return {**BOUNDARY, 'valid': True, 'binding_revision': row['revision'],
                'profile': 'edgeops-local-synthetic-v2-preflight-v1',
                'note': 'Preflight only; no measurement, receipt, inference or operational effect was stored.'}
