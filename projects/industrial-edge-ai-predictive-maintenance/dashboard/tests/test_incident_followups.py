"""Declared follow-up dates, scoped access, immutable history and recovery."""
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


class IncidentFollowupTests(unittest.TestCase):
    setUp=fixture.AcquisitionRegistryApiTests.setUp
    login=fixture.AcquisitionRegistryApiTests.login
    post=fixture.AcquisitionRegistryApiTests.post
    create=incident_fixture.IncidentApiTests.create
    action=incident_fixture.IncidentApiTests.action

    def save(self,row,due='2099-01-02T12:00:00+04:00',**changes):
        return self.post('/api/incidents/'+row['id']+'/follow-up',{'expected_revision':row['revision'],'due_at':due,'note':'Declare a follow-up date for this synthetic exercise.',**changes})

    def test_offset_normalization_history_and_persistence(self):
        row=self.create();result=self.save(row);self.assertEqual(result.status_code,200,result.text)
        data=result.json();self.assertFalse(data['external_notifications_sent'])
        self.assertEqual(data['incident']['follow_up']['due_at'],'2099-01-02T08:00:00.000000+00:00')
        self.assertEqual(data['incident']['follow_up']['status'],'upcoming')
        self.assertNotIn('status',data['history'][0]['follow_up'])
        self.server.init_db();self.assertEqual(self.http.get('/api/incidents/'+row['id']).json()['incident']['revision'],2)

    def test_strict_dates_and_unexpected_inputs(self):
        row=self.create()
        for date in ['2099-01-02T12:00:00','not a date','2101-01-01T00:00Z','1999-12-31T00:00Z','2099-02-30T12:00Z',True,123,'']:
            self.assertEqual(self.save(row,date).status_code,422,str(date))
        self.assertEqual(self.save(row,extra=True).status_code,422)
        self.assertEqual(self.save(row,expected_revision=True).status_code,422)

    def test_scoped_filters_and_clearing(self):
        none=self.create();over=self.save(self.create(),'2001-01-02T00:00:00Z').json()['incident'];up=self.save(self.create()).json()['incident']
        for state,expected in [('none',none),('overdue',over),('upcoming',up)]:
            result=self.http.get('/api/incidents?follow_up='+state).json()
            self.assertEqual([r['id'] for r in result['incidents']],[expected['id']])
        cleared=self.save(over,None);self.assertEqual(cleared.status_code,200)
        self.assertEqual(cleared.json()['incident']['follow_up']['status'],'none')
        self.login('operator');self.assertEqual(self.http.get('/api/incidents?follow_up=upcoming').json()['total'],0)
        self.assertEqual(self.save(up).status_code,404)
        self.assertEqual(self.http.get('/api/incidents?follow_up=invalid').status_code,422)

    def test_resolved_date_retained_and_reopen_becomes_overdue(self):
        row=self.save(self.create(),'2001-01-01T00:00:00Z').json()['incident']
        row=self.action(row,'acknowledge').json()['incident'];row=self.action(row,'resolve').json()['incident']
        self.assertEqual(row['follow_up']['status'],'resolved')
        self.assertEqual(self.http.get('/api/incidents?follow_up=overdue').json()['total'],0)
        self.assertEqual(self.save(row,None).status_code,409)
        row=self.action(row,'reopen').json()['incident'];self.assertEqual(row['follow_up']['status'],'overdue')

    def test_creator_assignee_and_readonly_roles(self):
        row=self.create()
        with self.server.database() as db:target=db.execute("SELECT id FROM users WHERE role='operator'").fetchone()[0]
        row=self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':1,'assignee_id':target,'note':'Assign this date exercise to the local operator.'}).json()['incident']
        self.login('operator');saved=self.save(row);self.assertEqual(saved.status_code,200)
        self.login('auditor');data=self.http.get('/api/incidents/'+row['id']).json()
        self.assertFalse(data['incident']['can_set_follow_up']);self.assertEqual(self.save(saved.json()['incident'],None).status_code,403)

    def test_csrf_session_and_capacity(self):
        row=self.create();body={'expected_revision':1,'due_at':None,'note':'A protected date change exercise.'}
        self.assertEqual(self.post('/api/incidents/'+row['id']+'/follow-up',body,csrf=False).status_code,403)
        with patch.object(incidents,'MAX_REVISIONS',1):self.assertEqual(self.save(row).status_code,409)
        original=incidents.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(incidents,'fresh_actor',side_effect=revoke):self.assertEqual(self.save(row).status_code,401)

    def test_concurrent_changes_and_noop_are_rejected(self):
        row=self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.save(row),range(2)))
        self.assertEqual(sorted(x.status_code for x in results),[200,409])
        row=self.http.get('/api/incidents/'+row['id']).json()['incident'];self.assertEqual(self.save(row).status_code,409)

    def test_linked_planning_context_keeps_captured_date(self):
        row=self.save(self.create()).json()['incident']
        plan=self.post('/api/incidents/'+row['id']+'/maintenance-plan',{'expected_revision':2,'proposal':'Inspect this synthetic source at its declared follow-up revision.'}).json()['request']
        changed=self.save(row,'2001-01-01T00:00:00Z');self.assertEqual(changed.status_code,200)
        source=self.http.get('/api/maintenance-requests/'+plan['id']).json()['source_incident']
        self.assertTrue(source['changed_since_capture'])
        self.assertEqual(source['snapshot']['follow_up']['due_at'],row['follow_up']['due_at'])
        self.assertNotIn('status',source['snapshot']['follow_up'])

    def test_audit_failure_rolls_back_date_and_revision(self):
        row=self.create()
        with self.server.database() as db:db.execute("CREATE TRIGGER fail_date_audit BEFORE INSERT ON audit WHEN NEW.action='synthetic_incident_follow_up_changed' BEGIN SELECT RAISE(ABORT,'test rollback'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.save(row)
        data=self.http.get('/api/incidents/'+row['id']).json();self.assertEqual(data['incident']['revision'],1)
        self.assertIsNone(data['incident']['follow_up']['due_at']);self.assertEqual(len(data['history']),1)

    def test_clock_reads_do_not_write_and_legacy_history_stays_unknown(self):
        row=self.create()
        with self.server.database() as db:
            snapshot=json.loads(db.execute('SELECT snapshot_json FROM synthetic_incident_events').fetchone()[0]);snapshot.pop('follow_up')
            db.execute('UPDATE synthetic_incident_events SET snapshot_json=?',(json.dumps(snapshot),))
        row=self.save(row).json()['incident']
        for _ in range(3):
            data=self.http.get('/api/incidents/'+row['id']).json();self.assertEqual(data['incident']['revision'],2)
            self.assertFalse(data['history'][-1]['follow_up_recorded']);self.assertEqual(len(data['history']),2)
        backup=Path(self.temp.name)/'backup';restored=Path(self.temp.name)/'restored'
        recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restored)
        with closing(sqlite3.connect(restored/'dashboard.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT due_at FROM incident_followups').fetchone()[0],row['follow_up']['due_at'])
