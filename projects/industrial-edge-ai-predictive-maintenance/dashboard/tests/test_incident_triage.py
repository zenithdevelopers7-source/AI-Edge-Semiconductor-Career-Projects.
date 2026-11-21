"""Declared severity review, original-context preservation and scoped queues."""
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
import test_incidents as cases


class IncidentTriageTests(unittest.TestCase):
    setUp=fixture.AcquisitionRegistryApiTests.setUp
    login=fixture.AcquisitionRegistryApiTests.login
    post=fixture.AcquisitionRegistryApiTests.post
    create=cases.IncidentApiTests.create
    action=cases.IncidentApiTests.action

    def review(self,row,severity='critical',**changes):
        return self.post('/api/incidents/'+row['id']+'/severity',{'expected_revision':row['revision'],'severity':severity,
            'note':'Review the declared severity using this synthetic investigation context.',**changes})

    def test_review_preserves_original_severity_observation_and_state(self):
        row=self.create();observation=row['observation']
        with self.server.database() as db:key=db.execute('SELECT request_key FROM synthetic_incidents').fetchone()[0]
        original={name:row[name] for name in ('asset_id','title','observation','severity','evidence_refs')}
        original.update(request_key=key,source_type='synthetic')
        for severity in ('critical','info','watch'):
            result=self.review(row,severity);self.assertEqual(result.status_code,200,result.text);data=result.json();row=data['incident']
            self.assertEqual(row['severity'],'watch');self.assertEqual(row['initial_severity'],'watch');self.assertEqual(row['current_severity'],severity)
            self.assertEqual(row['observation'],observation);self.assertEqual(row['state'],'open')
            self.assertFalse(data['equipment_authorized']);self.assertFalse(data['external_notifications_sent'])
            retry=self.post('/api/incidents',original)
            self.assertEqual(retry.status_code,200);self.assertFalse(retry.json()['created'])
            self.assertEqual(retry.json()['incident']['current_severity'],severity)
        self.server.init_db();history=self.http.get('/api/incidents/'+row['id']).json()['history']
        self.assertEqual([h['current_severity'] for h in history],['watch','info','critical','watch'])
        with self.server.database() as db:self.assertEqual(db.execute('SELECT severity FROM synthetic_incidents').fetchone()[0],'watch')

    def test_current_assignee_can_review_but_loses_access_after_handoff(self):
        row=self.create();self.login('operator');self.assertEqual(self.review(row).status_code,404);self.login('admin')
        with self.server.database() as db:target=db.execute("SELECT id FROM users WHERE role='operator'").fetchone()[0]
        row=self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':1,'assignee_id':target,'note':'Share the synthetic triage exercise with an operator.'}).json()['incident']
        self.login('operator');result=self.review(row);self.assertEqual(result.status_code,200);row=result.json()['incident']
        self.login('admin');row=self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':row['revision'],'assignee_id':None,'note':'Remove the temporary synthetic triage assignment.'}).json()['incident']
        self.login('operator');self.assertEqual(self.review(row,'info').status_code,404)

    def test_strict_inputs_readonly_auth_and_csrf(self):
        row=self.create()
        for changes in ({'severity':'emergency'},{'severity':True},{'expected_revision':True},{'note':'short'},{'note':'x'*801},{'extra':True}):
            body={'expected_revision':1,'severity':'critical','note':'A declared synthetic severity review reason.',**changes}
            self.assertEqual(self.post('/api/incidents/'+row['id']+'/severity',body).status_code,422)
        self.assertEqual(self.post('/api/incidents/'+row['id']+'/severity',{'expected_revision':1,'severity':'critical','note':'A protected synthetic severity review.'},csrf=False).status_code,403)
        self.login('auditor');self.assertFalse(self.http.get('/api/incidents/'+row['id']).json()['can_review_severity']);self.assertEqual(self.review(row).status_code,403)
        self.http.cookies.clear();self.assertEqual(self.http.post('/api/incidents/'+row['id']+'/severity',json={'expected_revision':1,'severity':'critical','note':'An unauthenticated synthetic review.'}).status_code,401)

    def test_concurrent_reviews_share_one_revision(self):
        row=self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda severity:self.review(row,severity),['critical','info']))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        data=self.http.get('/api/incidents/'+row['id']).json();self.assertEqual(len(data['history']),2);self.assertEqual(data['incident']['revision'],2)

    def test_noop_stale_resolved_and_capacity_guards(self):
        row=self.create();self.assertEqual(self.review(row,'watch').status_code,409)
        with patch.object(incidents,'MAX_REVISIONS',1):self.assertEqual(self.review(row).status_code,409)
        current=self.review(row).json()['incident'];self.assertEqual(self.review(row,'info').status_code,409)
        current=self.action(current,'acknowledge').json()['incident'];current=self.action(current,'resolve').json()['incident']
        self.assertEqual(self.review(current,'info').status_code,409)
        self.assertEqual(self.http.get('/api/incidents/'+row['id']).json()['incident']['current_severity'],'critical')
        current=self.action(current,'reopen').json()['incident'];self.assertEqual(self.review(current,'info').status_code,200)

    def test_audit_failure_rolls_back_triage_revision_and_history(self):
        row=self.create()
        with self.server.database() as db:db.execute("CREATE TRIGGER fail_triage BEFORE INSERT ON audit WHEN NEW.action='synthetic_incident_severity_reviewed' BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.review(row)
        data=self.http.get('/api/incidents/'+row['id']).json();self.assertEqual(data['incident']['revision'],1);self.assertEqual(len(data['history']),1)
        self.assertEqual(data['incident']['current_severity'],'watch')
        with self.server.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM incident_triage').fetchone()[0],0)

    def test_session_is_rechecked_under_write_lock(self):
        row=self.create();original=incidents.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(incidents,'fresh_actor',side_effect=revoke):self.assertEqual(self.review(row).status_code,401)

    def test_scoped_current_severity_filter_and_stable_order(self):
        watch=self.create();critical=self.review(self.create()).json()['incident'];info=self.review(self.create(),'info').json()['incident']
        with self.server.database() as db:db.execute("UPDATE synthetic_incidents SET updated_at='2026-11-20T10:00:00+00:00'")
        rows=self.http.get('/api/incidents?sort=severity').json()['incidents'];self.assertEqual([r['id'] for r in rows],[critical['id'],watch['id'],info['id']])
        for severity,row in [('critical',critical),('watch',watch),('info',info)]:
            page=self.http.get('/api/incidents?severity='+severity).json();self.assertEqual(page['total'],1);self.assertEqual(page['incidents'][0]['id'],row['id'])
        first=self.http.get('/api/incidents?sort=severity&limit=1').json();second=self.http.get('/api/incidents?sort=severity&limit=1&offset=1').json()
        self.assertEqual(first['incidents'][0]['id'],critical['id']);self.assertEqual(second['incidents'][0]['id'],watch['id'])
        self.login('operator');self.assertEqual(self.http.get('/api/incidents?severity=critical&sort=severity').json()['total'],0)
        for query in ('severity=urgent','sort=ascending'):
            self.assertEqual(self.http.get('/api/incidents?'+query).status_code,422)

    def test_plan_priority_uses_current_review_and_retains_frozen_context(self):
        row=self.review(self.create()).json()['incident']
        plan=self.post('/api/incidents/'+row['id']+'/maintenance-plan',{'expected_revision':row['revision'],'proposal':'Investigate the synthetic critical context under independent review.'}).json()
        self.assertEqual(plan['request']['priority'],'critical');self.assertEqual(plan['source_incident']['snapshot']['initial_severity'],'watch')
        self.assertEqual(plan['source_incident']['snapshot']['current_severity'],'critical')
        self.assertEqual(self.review(row,'info').status_code,200)
        saved=self.http.get('/api/maintenance-requests/'+plan['request']['id']).json()
        self.assertEqual(saved['request']['priority'],'critical');self.assertTrue(saved['source_incident']['changed_since_capture'])
        self.assertEqual(saved['source_incident']['snapshot']['current_severity'],'critical')

    def test_truthful_legacy_history_and_backup_restore(self):
        row=self.create()
        with self.server.database() as db:
            snapshot=json.loads(db.execute('SELECT snapshot_json FROM synthetic_incident_events').fetchone()[0]);snapshot.pop('initial_severity');snapshot.pop('current_severity')
            db.execute('UPDATE synthetic_incident_events SET snapshot_json=?',(json.dumps(snapshot),))
        data=self.review(row).json();self.assertFalse(data['history'][-1]['severity_recorded']);self.assertIsNone(data['history'][-1]['current_severity'])
        self.assertEqual(data['history'][-1]['initial_severity'],'watch')
        backup=Path(self.temp.name)/'backup';restore=Path(self.temp.name)/'restore';recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restore)
        with closing(sqlite3.connect(restore/'dashboard.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT severity FROM incident_triage').fetchone()[0],'critical')
            self.assertEqual(db.execute('SELECT severity FROM synthetic_incidents').fetchone()[0],'watch')
