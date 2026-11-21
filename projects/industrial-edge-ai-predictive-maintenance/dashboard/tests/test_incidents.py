"""Persistent synthetic incident boundaries; disposable databases only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import secrets
from pathlib import Path
import unittest
from unittest.mock import patch

import incidents
import recovery
import test_acquisition_registry as fixtures


def payload(**changes):
    return dict(request_key=secrets.token_hex(16),source_type='synthetic',asset_id='MTR-001',
                title='Synthetic vibration observation',observation='Synthetic exercise; no equipment fault is established.',
                severity='watch',evidence_refs='synthetic-fixture-001',**changes)


class IncidentApiTests(unittest.TestCase):
    login=fixtures.AcquisitionRegistryApiTests.login
    post=fixtures.AcquisitionRegistryApiTests.post
    def setUp(self): fixtures.AcquisitionRegistryApiTests.setUp(self)

    def create(self):
        result=self.post('/api/incidents',payload())
        self.assertEqual(result.status_code,200,result.text)
        return result.json()['incident']

    def action(self,row,action,**changes):
        body=dict(expected_revision=row['revision'],action=action,note='Synthetic exercise decision with a recorded explanation.',evidence_refs='synthetic-evidence-002')
        body.update(changes)
        return self.post('/api/incidents/'+row['id']+'/actions',body)

    def test_complete_lifecycle_is_saved_with_history_and_audit(self):
        row=self.create()
        for action,state in (('acknowledge','acknowledged'),('resolve','resolved'),('reopen','open')):
            result=self.action(row,action);self.assertEqual(result.status_code,200,result.text)
            data=result.json();row=data['incident'];self.assertEqual(row['state'],state)
            self.assertFalse(data['hardware_connected']);self.assertFalse(data['equipment_authorized'])
        self.server.init_db()
        data=self.http.get('/api/incidents/'+row['id']).json()
        self.assertEqual([x['action'] for x in data['history']],['reopen','resolve','acknowledge','create'])
        self.assertNotIn('request_key',data['incident'])
        with self.server.database() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE action LIKE 'synthetic_incident_%'").fetchone()[0],4)

    def test_idempotency_response_loss_retry_and_payload_conflict(self):
        body=payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.post('/api/incidents',body),range(2)))
        self.assertTrue(all(result.status_code==200 for result in results))
        self.assertEqual(sorted(result.json()['created'] for result in results),[False,True])
        self.assertEqual(self.post('/api/incidents',dict(body,title='Different synthetic incident')).status_code,409)
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM synthetic_incidents').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM synthetic_incident_events').fetchone()[0],1)

    def test_transition_order_stale_revision_and_resolution_evidence(self):
        row=self.create()
        self.assertEqual(self.action(row,'resolve').status_code,409)
        new=self.action(row,'acknowledge').json()['incident']
        self.assertEqual(self.action(row,'acknowledge').status_code,409)
        self.assertEqual(self.action(new,'resolve',evidence_refs=' ').status_code,422)
        self.assertEqual(self.action(new,'reopen').status_code,409)
        self.assertEqual(self.http.get('/api/incidents/'+row['id']).json()['incident']['revision'],2)

    def test_roles_creator_scope_csrf_and_unauthenticated_requests(self):
        admin=self.create()
        self.assertEqual(self.post('/api/incidents',payload(),csrf=False).status_code,403)
        self.login('operator')
        self.assertEqual(self.http.get('/api/incidents').json()['total'],0)
        self.assertEqual(self.http.get('/api/incidents/'+admin['id']).status_code,404)
        self.assertEqual(self.action(admin,'acknowledge').status_code,404)
        own=self.create();self.assertEqual(self.action(own,'acknowledge').status_code,200)
        self.login('auditor')
        self.assertEqual(self.http.get('/api/incidents').json()['total'],2)
        self.assertEqual(self.http.get('/api/incidents/'+own['id']).json()['incident']['actions'],[])
        self.assertEqual(self.post('/api/incidents',payload()).status_code,403)
        self.assertEqual(self.action(own,'acknowledge').status_code,403)
        self.http.cookies.clear()
        self.assertEqual(self.http.get('/api/incidents').status_code,401)
        self.assertEqual(self.post('/api/incidents',payload(),csrf=False).status_code,401)

    def test_real_sources_unknown_fields_and_bad_values_are_rejected(self):
        for changes in ({'source_type':'measured'},{'source_type':'replayed'},{'motor_command':'run'},
                        {'asset_id':'unknown'},{'severity':'urgent'},{'title':'     '}):
            body=payload();body.update(changes)
            self.assertEqual(self.post('/api/incidents',body).status_code,422)
        row=self.create()
        self.assertEqual(self.action(row,'acknowledge',expected_revision=True).status_code,422)
        self.assertEqual(self.action(row,'acknowledge',note='         ').status_code,422)

    def test_concurrent_steps_cannot_create_two_revisions(self):
        row=self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.action(row,'acknowledge').status_code,range(2)))
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(len(self.http.get('/api/incidents/'+row['id']).json()['history']),2)

    def test_session_is_rechecked_inside_the_write_transaction(self):
        row=self.create();original=incidents.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],))
            return original(db,current)
        with patch.object(incidents,'fresh_actor',side_effect=revoke):
            self.assertEqual(self.action(row,'acknowledge').status_code,401)
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT revision FROM synthetic_incidents').fetchone()[0],1)

    def test_audit_failure_rolls_back_domain_event_and_state(self):
        row=self.create()
        with self.server.database() as db:
            db.execute("CREATE TRIGGER deny_incident_audit BEFORE INSERT ON audit WHEN NEW.action LIKE 'synthetic_incident_%' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError): self.action(row,'acknowledge')
        data=self.http.get('/api/incidents/'+row['id']).json()
        self.assertEqual((data['incident']['revision'],len(data['history'])),(1,1))

    def test_filter_literal_search_pagination_and_capacity(self):
        self.create()
        self.assertEqual(self.http.get('/api/incidents?q=%25').json()['total'],0)
        self.assertEqual(self.http.get('/api/incidents?q=MTR-001').json()['total'],1)
        self.assertEqual(self.http.get('/api/incidents?offset=1&limit=1').json()['incidents'],[])
        self.assertEqual(self.http.get('/api/incidents?state=invalid').status_code,422)
        with patch.object(incidents,'MAX_INCIDENTS',1):
            self.assertEqual(self.post('/api/incidents',payload()).status_code,409)
        row=self.http.get('/api/incidents').json()['incidents'][0]
        with patch.object(incidents,'MAX_REVISIONS',1):
            self.assertEqual(self.action(row,'acknowledge').status_code,409)

    def test_backup_restore_preserves_incident_and_full_history(self):
        row=self.create();row=self.action(row,'acknowledge').json()['incident']
        row=self.action(row,'resolve').json()['incident']
        backup=Path(self.temp.name)/'backup';restored=Path(self.temp.name)/'restored'
        recovery.create_backup(self.server.DB_PATH,backup)
        recovery.restore_backup(backup,restored)
        with closing(sqlite3.connect(restored/'dashboard.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT state,revision FROM synthetic_incidents').fetchone(),('resolved',3))
            self.assertEqual(db.execute('SELECT count(*) FROM synthetic_incident_events').fetchone()[0],3)
            self.assertEqual(db.execute('SELECT count(*) FROM sessions').fetchone()[0],0)
