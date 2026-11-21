"""Administrator-managed local accounts; no invitations, identity-provider or equipment authority."""
from datetime import datetime, timezone
import re
import time
from typing import Literal

from fastapi import HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from maintenance_requests import fresh_actor, require_role

BOUNDARY = {'scope': 'local-team-administration', 'external_invitation_sent': False,
            'identity_verified': False, 'hardware_connected': False, 'equipment_authorized': False,
            'production_ready': False}
MAX_ACCOUNTS, MAX_REVISIONS = 100, 200


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(strict=True, min_length=1, max_length=256)
    reason: str = Field(strict=True, min_length=10, max_length=800)

    @field_validator('reason')
    @classmethod
    def reason_text(cls, value):
        if len(value.strip()) < 10: raise ValueError('Explain the account change in at least 10 characters')
        return value.strip()


class CreateAccount(StrictModel):
    email: str = Field(strict=True, min_length=5, max_length=254)
    role: Literal['admin','operator','auditor']
    initial_password: str = Field(strict=True, min_length=14, max_length=256)

    @field_validator('initial_password')
    @classmethod
    def nonblank_password(cls, value):
        if not value.strip(): raise ValueError('Initial password cannot be entirely whitespace')
        return value

    @field_validator('email')
    @classmethod
    def local_email(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9._+\-]{0,63}@[a-z0-9](?:[a-z0-9.\-]{0,185}[a-z0-9])?\.[a-z]{2,63}', value):
            raise ValueError('Use a supported ASCII email address')
        return value


class ChangeAccount(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    role: Literal['admin','operator','auditor']
    disabled: bool = Field(strict=True)


class RotatePassword(StrictModel):
    expected_revision: int = Field(strict=True, ge=1)
    new_password: str = Field(strict=True, min_length=14, max_length=256)

    @field_validator('new_password')
    @classmethod
    def nonblank_password(cls, value):
        if not value.strip(): raise ValueError('New password cannot be entirely whitespace')
        return value


def init_schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS account_controls(
        user_id INTEGER PRIMARY KEY REFERENCES users(id), revision INTEGER NOT NULL, updated_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS account_control_events(
        user_id INTEGER NOT NULL REFERENCES users(id), revision INTEGER NOT NULL,
        actor_id INTEGER NOT NULL REFERENCES users(id), actor_email TEXT NOT NULL, action TEXT NOT NULL,
        role TEXT NOT NULL, disabled INTEGER NOT NULL, reason TEXT NOT NULL, time_utc TEXT NOT NULL,
        PRIMARY KEY(user_id,revision))''')
    db.execute('''CREATE TABLE IF NOT EXISTS account_reauth_denials(
        actor_id INTEGER NOT NULL REFERENCES users(id), time_epoch INTEGER NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS account_denial_actor_time ON account_reauth_denials(actor_id,time_epoch)')


def present(row):
    return {'id': row['id'], 'email': row['email'], 'role': row['role'], 'disabled': bool(row['disabled']),
            'revision': row['revision'], 'updated_at': row['updated_at']}


def account(db, identifier):
    row = db.execute('''SELECT u.id,u.email,u.role,u.disabled,COALESCE(c.revision,1) revision,c.updated_at
        FROM users u LEFT JOIN account_controls c ON c.user_id=u.id WHERE u.id=?''', (identifier,)).fetchone()
    if not row: raise HTTPException(404, 'Local account not found')
    return row


def detail(db, row):
    events = db.execute('''SELECT revision,actor_email,action,role,disabled,reason,time_utc
        FROM account_control_events WHERE user_id=? ORDER BY revision DESC LIMIT ?''', (row['id'], MAX_REVISIONS)).fetchall()
    return {'account': present(row), 'history': [dict(event) for event in events], **BOUNDARY}


def reauthenticate(db, current, password, matches, audit):
    actor = fresh_actor(db, current); require_role(actor, ('admin',))
    now = int(time.time())
    if db.execute('SELECT count(*) FROM account_reauth_denials WHERE actor_id=? AND time_epoch>?', (actor['id'], now-900)).fetchone()[0] >= 5:
        raise HTTPException(429, 'Too many administrator password attempts; retry after the 15-minute window')
    expected = db.execute('SELECT password_hash FROM users WHERE id=?', (actor['id'],)).fetchone()[0]
    if not matches(password, expected):
        db.execute('DELETE FROM account_reauth_denials WHERE time_epoch<=?', (now-900,))
        db.execute('INSERT INTO account_reauth_denials VALUES(?,?)', (actor['id'], now))
        audit(db, actor['email'], 'team_reauthentication_failed', 'administrator password verification denied')
        db.commit()  # Persist denial/rate limiting before the HTTP exception; no account change has occurred.
        raise HTTPException(403, 'Administrator password could not be verified')
    db.execute('DELETE FROM account_reauth_denials WHERE actor_id=? OR time_epoch<=?', (actor['id'], now-900))
    return actor


def event(db, row, actor, action, reason, audit):
    db.execute('INSERT INTO account_control_events VALUES(?,?,?,?,?,?,?,?,?)',
        (row['id'], row['revision'], actor['id'], actor['email'], action, row['role'], row['disabled'], reason, row['updated_at']))
    audit(db, actor['email'], 'team_account_' + action, 'account_id=' + str(row['id']) + '; revision=' + str(row['revision']))


def install_routes(app, database, require_user, require_csrf, hash_password, matches, audit):
    @app.post('/api/team/{identifier}/password')
    def rotate_password(identifier: int, body: RotatePassword, request: Request):
        current = require_user(request); require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = reauthenticate(db, current, body.current_password, matches, audit)
            row = account(db, identifier)
            if row['revision'] != body.expected_revision: raise HTTPException(409, 'Account changed; reload the current revision before changing its password')
            if row['revision'] >= MAX_REVISIONS: raise HTTPException(409, 'Account history capacity reached; no password was changed')
            old_hash = db.execute('SELECT password_hash FROM users WHERE id=?', (identifier,)).fetchone()[0]
            if matches(body.new_password, old_hash): raise HTTPException(409, 'Choose a different new password; the current password was retained')
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(body.new_password), identifier))
            now = datetime.now(timezone.utc).isoformat()
            db.execute('''INSERT INTO account_controls VALUES(?,?,?) ON CONFLICT(user_id)
                DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at''', (identifier, row['revision']+1, now))
            revoked = db.execute('DELETE FROM sessions WHERE user_id=?', (identifier,)).rowcount
            row = account(db, identifier); event(db, row, actor, 'password_changed', body.reason, audit)
            return {**detail(db, row), 'sessions_revoked': revoked,
                    'sign_in_again': actor['id'] == identifier, 'password_changed': True}

    @app.get('/api/team')
    def list_accounts(request: Request, q: str = Query(default='', max_length=160),
                      offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=50)):
        actor = require_user(request); require_role(actor, ('admin',))
        query = '%' + q.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
        with database() as db:
            db.execute('BEGIN')
            total = db.execute("SELECT count(*) FROM users WHERE email LIKE ? ESCAPE '\\'", (query,)).fetchone()[0]
            rows = db.execute('''SELECT u.id,u.email,u.role,u.disabled,COALESCE(c.revision,1) revision,c.updated_at
                FROM users u LEFT JOIN account_controls c ON c.user_id=u.id
                WHERE u.email LIKE ? ESCAPE '\\' ORDER BY u.id LIMIT ? OFFSET ?''', (query, limit, offset)).fetchall()
        return {'accounts': [present(row) for row in rows], 'total': total, 'offset': offset, 'limit': limit,
                'current_account_id': actor['id'], **BOUNDARY}

    @app.get('/api/team/{identifier}')
    def get_account(identifier: int, request: Request):
        actor = require_user(request); require_role(actor, ('admin',))
        with database() as db:
            db.execute('BEGIN'); return detail(db, account(db, identifier))

    @app.post('/api/team')
    def create(body: CreateAccount, request: Request):
        current = require_user(request); require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = reauthenticate(db, current, body.current_password, matches, audit)
            if db.execute('SELECT 1 FROM users WHERE email=?', (body.email,)).fetchone(): raise HTTPException(409, 'A local account already uses this email; no password was changed')
            if db.execute('SELECT count(*) FROM users').fetchone()[0] >= MAX_ACCOUNTS: raise HTTPException(409, 'Local account capacity reached; no accounts were removed')
            identifier = db.execute('INSERT INTO users(email,password_hash,role,disabled) VALUES(?,?,?,0)',
                (body.email, hash_password(body.initial_password), body.role)).lastrowid
            now = datetime.now(timezone.utc).isoformat()
            db.execute('INSERT INTO account_controls VALUES(?,1,?)', (identifier, now))
            row = account(db, identifier); event(db, row, actor, 'created', body.reason, audit)
            return {**detail(db, row), 'created': True}

    @app.post('/api/team/{identifier}')
    def change(identifier: int, body: ChangeAccount, request: Request):
        current = require_user(request); require_csrf(request, current)
        with database() as db:
            db.execute('BEGIN IMMEDIATE')
            actor = reauthenticate(db, current, body.current_password, matches, audit)
            row = account(db, identifier)
            if row['revision'] != body.expected_revision: raise HTTPException(409, 'Account changed; reload the current revision')
            if row['revision'] >= MAX_REVISIONS: raise HTTPException(409, 'Account history capacity reached; no records were deleted')
            if row['role'] == body.role and bool(row['disabled']) == body.disabled: raise HTTPException(409, 'No account change was requested')
            if row['role'] == 'admin' and not row['disabled'] and (body.role != 'admin' or body.disabled):
                if db.execute("SELECT count(*) FROM users WHERE role='admin' AND disabled=0").fetchone()[0] <= 1:
                    raise HTTPException(409, 'Keep at least one active administrator; the last active administrator cannot be disabled or demoted')
            now = datetime.now(timezone.utc).isoformat(); revision = row['revision'] + 1
            db.execute('UPDATE users SET role=?,disabled=? WHERE id=?', (body.role, int(body.disabled), identifier))
            db.execute('''INSERT INTO account_controls VALUES(?,?,?) ON CONFLICT(user_id)
                DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at''', (identifier, revision, now))
            revoked = db.execute('DELETE FROM sessions WHERE user_id=?', (identifier,)).rowcount
            row = account(db, identifier); event(db, row, actor, 'changed', body.reason, audit)
            return {**detail(db, row), 'sessions_revoked': revoked, 'sign_in_again': actor['id'] == identifier}
