"""Local account management in disposable stores; no real account is created."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import secrets
import sqlite3
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import recovery
import team_accounts
import test_acquisition_registry as fixture


class TeamAccountTests(unittest.TestCase):
    login=fixture.AcquisitionRegistryApiTests.login
    post=fixture.AcquisitionRegistryApiTests.post
    def setUp(self):fixture.AcquisitionRegistryApiTests.setUp(self)

    def create_body(self,**changes):
        return {'email':'new-reviewer@example.invalid','role':'admin','initial_password':secrets.token_urlsafe(24),
                'current_password':self.password,'reason':'Create a separate local account for independent review.',**changes}

    def account(self,email):
        return next(row for row in self.http.get('/api/team').json()['accounts'] if row['email']==email)

    def change(self,row,**changes):
        body={'expected_revision':row['revision'],'role':row['role'],'disabled':row['disabled'],
              'current_password':self.password,'reason':'Change local access for the recorded review workflow.',**changes}
        return self.post('/api/team/'+str(row['id']),body)

    def test_create_hashes_secret_returns_only_metadata_and_allows_independent_login(self):
        body=self.create_body();response=self.post('/api/team',body);self.assertEqual(response.status_code,200,response.text)
        data=response.json();self.assertFalse(data['external_invitation_sent']);self.assertFalse(data['identity_verified'])
        self.assertNotIn(body['initial_password'],json.dumps(data));self.assertNotIn('password_hash',json.dumps(data))
        with self.server.database() as db:
            stored=db.execute('SELECT password_hash FROM users WHERE email=?',(body['email'],)).fetchone()[0]
            self.assertNotEqual(stored,body['initial_password']);self.assertTrue(self.server.password_matches(body['initial_password'],stored))
        new=TestClient(self.server.app);self.addCleanup(new.close)
        self.assertEqual(new.post('/api/auth/login',json={'email':body['email'],'password':body['initial_password']}).status_code,200)

    def test_roles_csrf_and_unauthenticated_account_listing(self):
        self.assertEqual(self.post('/api/team',self.create_body(),csrf=False).status_code,403)
        for role in ('operator','auditor'):
            self.login(role);self.assertEqual(self.http.get('/api/team').status_code,403)
            self.assertEqual(self.post('/api/team',self.create_body()).status_code,403)
        self.http.cookies.clear();self.assertEqual(self.http.get('/api/team').status_code,401)
        self.login('admin');original=team_accounts.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(team_accounts,'fresh_actor',side_effect=revoke):
            self.assertEqual(self.post('/api/team',self.create_body()).status_code,401)

    def test_wrong_administrator_password_is_persisted_rate_limited_and_never_audited_raw(self):
        wrong='wrong-admin-password-for-test-only'
        for _ in range(5):self.assertEqual(self.post('/api/team',self.create_body(current_password=wrong)).status_code,403)
        self.assertEqual(self.post('/api/team',self.create_body()).status_code,429)
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM account_reauth_denials').fetchone()[0],5)
            notes=' '.join(row[0] for row in db.execute("SELECT detail FROM audit WHERE action='team_reauthentication_failed'"))
            self.assertNotIn(wrong,notes)
            self.assertEqual(db.execute("SELECT count(*) FROM users WHERE email='new-reviewer@example.invalid'").fetchone()[0],0)

    def test_last_active_admin_cannot_be_disabled_or_demoted(self):
        row=self.account('admin@example.invalid')
        self.assertEqual(self.change(row,disabled=True).status_code,409)
        self.assertEqual(self.change(row,role='operator').status_code,409)
        self.assertEqual(self.account('admin@example.invalid')['role'],'admin')

    def test_role_change_revokes_sessions_and_history_is_saved(self):
        operator=TestClient(self.server.app);self.addCleanup(operator.close)
        self.assertEqual(operator.post('/api/auth/login',json={'email':'operator@example.invalid','password':self.password}).status_code,200)
        row=self.account('operator@example.invalid');result=self.change(row,role='auditor')
        self.assertEqual(result.status_code,200);self.assertGreater(result.json()['sessions_revoked'],0)
        self.assertEqual(operator.get('/api/me').status_code,401)
        detail=self.http.get('/api/team/'+str(row['id'])).json()
        self.assertEqual(detail['account']['revision'],2);self.assertEqual(detail['history'][0]['role'],'auditor')
        self.assertEqual(self.change(row,disabled=True).status_code,409)

    def test_duplicate_email_and_concurrent_edits_never_overwrite_credentials(self):
        first=self.create_body();self.post('/api/team',first)
        self.assertEqual(self.post('/api/team',self.create_body(email=' NEW-REVIEWER@example.invalid ')).status_code,409)
        row=self.account('operator@example.invalid')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.change(row,disabled=True).status_code,range(2)))
        self.assertEqual(sorted(results),[200,409])
        with self.server.database() as db:
            saved=db.execute('SELECT password_hash FROM users WHERE email=?',(first['email'],)).fetchone()[0]
            self.assertTrue(self.server.password_matches(first['initial_password'],saved))

    def test_self_demotion_with_another_admin_ends_the_current_session(self):
        self.assertEqual(self.post('/api/team',self.create_body()).status_code,200)
        row=self.account('admin@example.invalid');result=self.change(row,role='operator')
        self.assertEqual(result.status_code,200);self.assertTrue(result.json()['sign_in_again'])
        self.assertEqual(self.http.get('/api/team').status_code,401)

    def test_disabled_account_cannot_log_in_and_authored_records_are_retained(self):
        self.login('operator');created=self.post('/api/incidents',{'request_key':secrets.token_hex(16),'source_type':'synthetic','asset_id':'MTR-001','title':'Synthetic owned record','observation':'Retain this synthetic record after disabling its author.','severity':'info'}).json()['incident']
        self.login('admin');row=self.account('operator@example.invalid');self.assertEqual(self.change(row,disabled=True).status_code,200)
        other=TestClient(self.server.app);self.addCleanup(other.close)
        self.assertEqual(other.post('/api/auth/login',json={'email':row['email'],'password':self.password}).status_code,401)
        self.assertEqual(self.http.get('/api/incidents/'+created['id']).status_code,200)

    def test_strict_inputs_capacity_and_audit_failure_rollback(self):
        for changes in ({'role':'root'},{'initial_password':'short'},{'initial_password':' '*14},{'email':'not-an-email'},{'reason':'   '},{'hardware_connected':True}):
            self.assertEqual(self.post('/api/team',self.create_body(**changes)).status_code,422)
        with patch.object(team_accounts,'MAX_ACCOUNTS',3):self.assertEqual(self.post('/api/team',self.create_body()).status_code,409)
        row=self.account('operator@example.invalid')
        with patch.object(team_accounts,'MAX_REVISIONS',1):self.assertEqual(self.change(row,disabled=True).status_code,409)
        with self.server.database() as db:db.execute("CREATE TRIGGER deny_team_audit BEFORE INSERT ON audit WHEN NEW.action='team_account_created' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.post('/api/team',self.create_body())
        with self.server.database() as db:self.assertEqual(db.execute("SELECT count(*) FROM users WHERE email='new-reviewer@example.invalid'").fetchone()[0],0)

    def test_backup_restores_accounts_and_management_history(self):
        self.post('/api/team',self.create_body());backup=Path(self.temp.name)/'backup';restored=Path(self.temp.name)/'restore'
        recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restored)
        with closing(sqlite3.connect(restored/'dashboard.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM account_control_events').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)

    def test_demotion_hides_current_foreign_incident_state_but_retains_captured_plan_context(self):
        self.login('operator');incident=self.post('/api/incidents',{'request_key':secrets.token_hex(16),'source_type':'synthetic','asset_id':'MTR-001','title':'Other operator incident','observation':'Synthetic source context owned by a different account.','severity':'watch'}).json()['incident']
        self.login('admin');plan=self.post('/api/incidents/'+incident['id']+'/maintenance-plan',{'expected_revision':1,'proposal':'Review this captured synthetic context without equipment authorization.'}).json()['request']
        self.post('/api/team',self.create_body());self.change(self.account('admin@example.invalid'),role='operator')
        self.login('admin')  # Same identity/password, now an operator after explicit demotion.
        self.assertEqual(self.http.get('/api/incidents/'+incident['id']).status_code,404)
        source=self.http.get('/api/maintenance-requests/'+plan['id']).json()['source_incident']
        self.assertFalse(source['current_accessible']);self.assertIsNone(source['current_revision']);self.assertIsNone(source['current_state'])
        self.assertEqual(source['snapshot']['observation'],incident['observation'])
