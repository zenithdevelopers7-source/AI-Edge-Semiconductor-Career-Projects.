"""Scoped synthetic incident ownership; no notifications or physical tasks."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import incidents
import recovery
import test_acquisition_registry as fixture
import test_incidents as incident_fixture


class IncidentAssignmentTests(unittest.TestCase):
    login=fixture.AcquisitionRegistryApiTests.login
    post=fixture.AcquisitionRegistryApiTests.post
    create=incident_fixture.IncidentApiTests.create
    action=incident_fixture.IncidentApiTests.action
    def setUp(self):
        fixture.AcquisitionRegistryApiTests.setUp(self)
        with self.server.database() as db:
            encoded=db.execute("SELECT password_hash FROM users WHERE role='operator'").fetchone()[0]
            db.execute("INSERT INTO users(email,password_hash,role) VALUES('other@example.invalid',?,'operator')",(encoded,))
            self.ids={row['email'].split('@')[0]:row['id'] for row in db.execute('SELECT id,email FROM users')}

    def assign(self,row,target,**changes):
        return self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':row['revision'],'assignee_id':target,
            'note':'Assign this synthetic incident for a local documentation exercise.',**changes})

    def test_assignment_grants_scoped_visibility_actions_and_planning(self):
        row=self.create();result=self.assign(row,self.ids['operator']);self.assertEqual(result.status_code,200,result.text)
        self.assertFalse(result.json()['external_notifications_sent']);row=result.json()['incident']
        self.login('operator');self.assertEqual(self.http.get('/api/incidents?ownership=assigned').json()['total'],1)
        self.assertEqual(self.http.get('/api/incidents?ownership=created').json()['total'],0)
        detail=self.http.get('/api/incidents/'+row['id']).json();self.assertIn('acknowledge',detail['incident']['actions'])
        self.assertFalse(detail['incident']['can_assign'])
        linked=self.post('/api/incidents/'+row['id']+'/maintenance-plan',{'expected_revision':row['revision'],'proposal':'Inspect the assigned synthetic context and its declared references.'})
        self.assertEqual(linked.status_code,200);self.assertTrue(linked.json()['source_incident']['current_accessible'])

    def test_assignee_cannot_forward_access_and_unrelated_operator_cannot_read(self):
        row=self.assign(self.create(),self.ids['operator']).json()['incident']
        self.login('operator');self.assertEqual(self.assign(row,self.ids['other']).status_code,403)
        self.assertEqual(self.http.get('/api/incidents/'+row['id']+'/assignment-candidates').status_code,403)
        self.http.cookies.clear();self.assertEqual(self.http.post('/api/auth/login',json={'email':'other@example.invalid','password':self.password}).status_code,200)
        self.assertEqual(self.http.get('/api/incidents/'+row['id']).status_code,404)
        self.assertEqual(self.http.get('/api/incidents').json()['total'],0)

    def test_reassignment_revokes_live_source_access_but_preserves_owned_plan_snapshot(self):
        row=self.assign(self.create(),self.ids['operator']).json()['incident'];self.login('operator')
        plan=self.post('/api/incidents/'+row['id']+'/maintenance-plan',{'expected_revision':row['revision'],'proposal':'Retain this assigned synthetic source as a planning snapshot.'}).json()['request']
        self.login('admin');row=self.assign(row,self.ids['other']).json()['incident'];self.login('operator')
        self.assertEqual(self.http.get('/api/incidents/'+row['id']).status_code,404)
        source=self.http.get('/api/maintenance-requests/'+plan['id']).json()['source_incident']
        self.assertFalse(source['current_accessible']);self.assertIsNone(source['current_state'])
        self.assertEqual(source['snapshot']['assignment']['user_id'],self.ids['operator'])

    def test_creator_operator_can_assign_and_unassign_without_changing_authorship(self):
        self.login('operator');row=self.create();row=self.assign(row,self.ids['other']).json()['incident']
        result=self.assign(row,None);self.assertEqual(result.status_code,200)
        self.assertIsNone(result.json()['incident']['assignment'])
        self.assertEqual(result.json()['incident']['creator_email'],'operator@example.invalid')
        self.assertEqual([item['action'] for item in result.json()['history']],['unassigned','assigned','create'])
        self.assertEqual(result.json()['history'][1]['assignment']['user_id'],self.ids['other'])

    def test_candidates_and_assignment_exclude_disabled_auditor_and_unknown_accounts(self):
        row=self.create()
        with self.server.database() as db:db.execute('UPDATE users SET disabled=1 WHERE id=?',(self.ids['other'],))
        candidates=self.http.get('/api/incidents/'+row['id']+'/assignment-candidates').json()['candidates']
        self.assertEqual({item['id'] for item in candidates},{self.ids['admin'],self.ids['operator']})
        for target in (self.ids['other'],self.ids['auditor'],99999):self.assertEqual(self.assign(row,target).status_code,422)

    def test_concurrent_assignment_and_acknowledgement_share_one_revision(self):
        row=self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=[pool.submit(self.assign,row,self.ids['operator']),pool.submit(self.action,row,'acknowledge')]
            codes=[item.result().status_code for item in results]
        self.assertEqual(sorted(codes),[200,409])
        self.assertEqual(self.http.get('/api/incidents/'+row['id']).json()['incident']['revision'],2)

    def test_audit_failure_rolls_back_assignment_revision_and_history(self):
        row=self.create()
        with self.server.database() as db:db.execute("CREATE TRIGGER deny_assignment_audit BEFORE INSERT ON audit WHEN NEW.action='synthetic_incident_assigned' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.assign(row,self.ids['operator'])
        data=self.http.get('/api/incidents/'+row['id']).json()
        self.assertIsNone(data['incident']['assignment']);self.assertEqual((data['incident']['revision'],len(data['history'])),(1,1))

    def test_auth_csrf_strict_payload_resolved_state_and_capacity(self):
        row=self.create()
        self.assertEqual(self.assign(row,True).status_code,422)
        self.assertEqual(self.assign(row,self.ids['operator'],expected_revision=True).status_code,422)
        self.assertEqual(self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':1,'assignee_id':self.ids['operator'],'note':'An unprotected write must be rejected.'},csrf=False).status_code,403)
        with patch.object(incidents,'MAX_REVISIONS',1):self.assertEqual(self.assign(row,self.ids['operator']).status_code,409)
        row=self.action(row,'acknowledge').json()['incident'];row=self.action(row,'resolve').json()['incident']
        self.assertEqual(self.assign(row,self.ids['operator']).status_code,409)
        self.login('auditor');self.assertEqual(self.assign(row,self.ids['operator']).status_code,403)

    def test_disabled_assignee_remains_recorded_as_unavailable_without_reassigning(self):
        row=self.assign(self.create(),self.ids['operator']).json()['incident']
        with self.server.database() as db:db.execute('UPDATE users SET disabled=1 WHERE id=?',(self.ids['operator'],))
        detail=self.http.get('/api/incidents/'+row['id']).json()
        self.assertFalse(detail['incident']['assignment']['eligible'])
        self.assertEqual(detail['incident']['assignment']['user_id'],self.ids['operator'])
        self.assertEqual(detail['incident']['revision'],2)

    def test_backup_restore_and_legacy_event_history_are_truthful(self):
        row=self.create()
        with self.server.database() as db:
            old=json.loads(db.execute('SELECT snapshot_json FROM synthetic_incident_events WHERE incident_id=?',(row['id'],)).fetchone()[0]);old.pop('assignment',None)
            db.execute('UPDATE synthetic_incident_events SET snapshot_json=? WHERE incident_id=?',(json.dumps(old),row['id']))
        row=self.assign(row,self.ids['operator']).json()['incident']
        self.assertFalse(self.http.get('/api/incidents/'+row['id']).json()['history'][-1]['assignment_recorded'])
        backup=Path(self.temp.name)/'backup';restored=Path(self.temp.name)/'restore';recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restored)
        with closing(sqlite3.connect(restored/'dashboard.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT assignee_id FROM incident_assignments').fetchone()[0],self.ids['operator'])
            self.assertEqual(db.execute('SELECT count(*) FROM synthetic_incident_events').fetchone()[0],2)

    def test_session_is_rechecked_inside_assignment_transaction(self):
        row=self.create();original=incidents.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(incidents,'fresh_actor',side_effect=revoke):self.assertEqual(self.assign(row,self.ids['operator']).status_code,401)
