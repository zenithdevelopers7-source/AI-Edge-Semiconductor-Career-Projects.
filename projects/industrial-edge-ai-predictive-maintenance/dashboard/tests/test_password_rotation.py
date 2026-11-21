"""Explicit administrator password rotation using disposable credentials only."""
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
import test_team_accounts as fixture


class PasswordRotationTests(unittest.TestCase):
    setUp=fixture.TeamAccountTests.setUp
    login=fixture.TeamAccountTests.login
    post=fixture.TeamAccountTests.post
    account=fixture.TeamAccountTests.account
    change=fixture.TeamAccountTests.change

    def rotate(self,row,secret,**changes):
        return self.post('/api/team/'+str(row['id'])+'/password',{
            'expected_revision':row['revision'],'new_password':secret,'current_password':self.password,
            'reason':'Rotate this disposable local credential for the account workflow test.',**changes})

    def test_rotation_replaces_hash_revokes_sessions_and_preserves_role_and_access(self):
        target=TestClient(self.server.app);self.addCleanup(target.close)
        target.post('/api/auth/login',json={'email':'operator@example.invalid','password':self.password})
        row=self.account('operator@example.invalid');new=secrets.token_urlsafe(24)
        result=self.rotate(row,new);self.assertEqual(result.status_code,200,result.text);data=result.json()
        self.assertTrue(data['password_changed']);self.assertFalse(data['sign_in_again']);self.assertGreater(data['sessions_revoked'],0)
        self.assertEqual((data['account']['role'],data['account']['disabled']),('operator',False))
        self.assertNotIn(new,json.dumps(data));self.assertNotIn('password_hash',json.dumps(data))
        self.assertEqual(target.get('/api/me').status_code,401)
        self.assertEqual(target.post('/api/auth/login',json={'email':row['email'],'password':self.password}).status_code,401)
        self.assertEqual(target.post('/api/auth/login',json={'email':row['email'],'password':new}).status_code,200)

    def test_self_rotation_ends_current_session_without_removing_last_admin(self):
        row=self.account('admin@example.invalid');result=self.rotate(row,secrets.token_urlsafe(24))
        self.assertEqual(result.status_code,200);self.assertTrue(result.json()['sign_in_again'])
        self.assertEqual(self.http.get('/api/me').status_code,401)
        with self.server.database() as db:self.assertEqual(db.execute("SELECT count(*) FROM users WHERE role='admin' AND disabled=0").fetchone()[0],1)

    def test_inflight_old_password_login_cannot_issue_a_session_after_rotation(self):
        row=self.account('operator@example.invalid');new=secrets.token_urlsafe(24)
        original=self.server.password_matches;changed=False
        def rotate_during_check(password,expected):
            nonlocal changed
            result=original(password,expected)
            if not changed:
                changed=True
                self.assertEqual(self.rotate(row,new).status_code,200)
            return result
        target=TestClient(self.server.app);self.addCleanup(target.close)
        with patch.object(self.server,'password_matches',side_effect=rotate_during_check):
            response=target.post('/api/auth/login',json={'email':row['email'],'password':self.password})
        self.assertEqual(response.status_code,401)
        with self.server.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM sessions WHERE user_id=?',(row['id'],)).fetchone()[0],0)

    def test_roles_csrf_reauthentication_and_strict_new_password(self):
        row=self.account('operator@example.invalid');new=secrets.token_urlsafe(24)
        for value in ('short',' '*14,self.password):
            self.assertIn(self.rotate(row,value).status_code,(409,422))
        self.assertEqual(self.rotate(row,new,expected_revision=True).status_code,422)
        self.assertEqual(self.rotate(row,new,hardware_connected=True).status_code,422)
        self.assertEqual(self.rotate(row,new,current_password='wrong-admin-password').status_code,403)
        self.assertEqual(self.post('/api/team/'+str(row['id'])+'/password',{'expected_revision':1,'new_password':new,'current_password':self.password,'reason':'A request without CSRF must be refused.'},csrf=False).status_code,403)
        for role in ('operator','auditor'):
            self.login(role);self.assertEqual(self.rotate(row,new).status_code,403)

    def test_concurrent_role_change_and_rotation_share_the_account_revision(self):
        row=self.account('operator@example.invalid');new=secrets.token_urlsafe(24)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.rotate,row,new),pool.submit(self.change,row,role='auditor')]
            results=[future.result().status_code for future in futures]
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(self.account(row['email'])['revision'],2)
        with self.server.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM account_control_events WHERE user_id=?',(row['id'],)).fetchone()[0],1)

    def test_audit_failure_rolls_back_password_revision_and_session_revocation(self):
        row=self.account('operator@example.invalid');target=TestClient(self.server.app);self.addCleanup(target.close)
        target.post('/api/auth/login',json={'email':row['email'],'password':self.password})
        with self.server.database() as db:db.execute("CREATE TRIGGER deny_password_audit BEFORE INSERT ON audit WHEN NEW.action='team_account_password_changed' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.rotate(row,secrets.token_urlsafe(24))
        self.assertEqual(target.get('/api/me').status_code,200);self.assertEqual(self.account(row['email'])['revision'],1)
        with self.server.database() as db:
            saved=db.execute('SELECT password_hash FROM users WHERE id=?',(row['id'],)).fetchone()[0]
            self.assertTrue(self.server.password_matches(self.password,saved))

    def test_disabled_target_stays_disabled_and_password_whitespace_is_preserved(self):
        row=self.account('operator@example.invalid');row=self.change(row,disabled=True).json()['account']
        new='  '+secrets.token_urlsafe(24)+'  ';result=self.rotate(row,new)
        self.assertEqual(result.status_code,200);self.assertTrue(result.json()['account']['disabled'])
        with self.server.database() as db:
            saved=db.execute('SELECT password_hash FROM users WHERE id=?',(row['id'],)).fetchone()[0]
            self.assertTrue(self.server.password_matches(new,saved));self.assertFalse(self.server.password_matches(new.strip(),saved))

    def test_session_revocation_capacity_and_failed_reauthentication_limits_apply(self):
        row=self.account('operator@example.invalid');original=team_accounts.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(team_accounts,'fresh_actor',side_effect=revoke):self.assertEqual(self.rotate(row,secrets.token_urlsafe(24)).status_code,401)
        with patch.object(team_accounts,'MAX_REVISIONS',1):self.assertEqual(self.rotate(row,secrets.token_urlsafe(24)).status_code,409)
        for _ in range(5):self.assertEqual(self.rotate(row,secrets.token_urlsafe(24),current_password='wrong-admin-password').status_code,403)
        self.assertEqual(self.rotate(row,secrets.token_urlsafe(24)).status_code,429)

    def test_restored_store_retains_rotated_hash_and_password_change_history(self):
        row=self.account('operator@example.invalid');new=secrets.token_urlsafe(24);self.rotate(row,new)
        backup=Path(self.temp.name)/'backup';restored=Path(self.temp.name)/'restore'
        recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restored)
        with closing(sqlite3.connect(restored/'dashboard.sqlite3')) as db:
            saved=db.execute('SELECT password_hash FROM users WHERE id=?',(row['id'],)).fetchone()[0]
            self.assertTrue(self.server.password_matches(new,saved))
            self.assertEqual(db.execute('SELECT action FROM account_control_events WHERE user_id=?',(row['id'],)).fetchone()[0],'password_changed')
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)
