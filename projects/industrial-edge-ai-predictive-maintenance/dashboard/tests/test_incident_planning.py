"""Atomic, scoped links between synthetic incidents and reviewed planning drafts."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import incidents
import recovery
import test_acquisition_registry as fixtures
import test_incidents as incident_fixtures


class IncidentPlanningTests(unittest.TestCase):
    login=fixtures.AcquisitionRegistryApiTests.login
    post=fixtures.AcquisitionRegistryApiTests.post
    create=incident_fixtures.IncidentApiTests.create
    action=incident_fixtures.IncidentApiTests.action
    def setUp(self):fixtures.AcquisitionRegistryApiTests.setUp(self)

    def link(self,row,**changes):
        body=dict(expected_revision=row['revision'],proposal='Inspect the synthetic observation provenance and recorded calibration context.')
        body.update(changes)
        return self.post('/api/incidents/'+row['id']+'/maintenance-plan',body)

    def fields(self,row,**changes):
        result={name:row[name] for name in ('asset_id','title','observation','proposal','evidence_refs','priority')}
        result.update(expected_revision=row['revision'],**changes)
        return result

    def test_atomic_creation_preserves_source_revision_without_changing_incident(self):
        incident=self.create();response=self.link(incident);self.assertEqual(response.status_code,200,response.text)
        data=response.json();plan=data['request'];source=data['source_incident']
        self.assertEqual((plan['asset_id'],plan['status'],plan['revision']),('MTR-001','draft',1))
        self.assertEqual(source['snapshot']['observation'],incident['observation'])
        self.assertEqual(source['revision'],1);self.assertFalse(data['execution_enabled'])
        original=self.http.get('/api/incidents/'+incident['id']).json()
        self.assertEqual(original['incident']['revision'],1)
        self.assertEqual(original['linked_plans'][0]['id'],plan['id'])
        self.assertFalse(original['can_prepare_plan'])

    def test_response_loss_and_concurrent_retries_do_not_duplicate_plans(self):
        incident=self.create()
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:self.link(incident),range(2)))
        self.assertTrue(all(response.status_code==200 for response in responses))
        self.assertEqual(sorted(response.json()['created'] for response in responses),[False,True])
        self.assertEqual(self.link(incident,proposal='A changed proposal must not create a second linked draft.').status_code,409)
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM incident_plan_links').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM maintenance_requests').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT count(*) FROM maintenance_request_events').fetchone()[0],1)
        self.action(incident,'acknowledge')
        retry=self.link(incident)
        self.assertFalse(retry.json()['created'])
        self.assertTrue(retry.json()['source_incident']['changed_since_capture'])

    def test_stale_and_resolved_incidents_refuse_new_links(self):
        incident=self.create();current=self.action(incident,'acknowledge').json()['incident']
        self.assertEqual(self.link(incident).status_code,409)
        current=self.action(current,'resolve').json()['incident']
        self.assertEqual(self.link(current).status_code,409)

    def test_permissions_csrf_and_link_visibility_follow_both_record_scopes(self):
        incident=self.create();self.link(incident)
        self.login('operator');self.assertEqual(self.link(incident).status_code,404)
        own=self.create();self.assertEqual(self.link(own).status_code,200)
        self.login('admin');self.assertEqual(self.link(own).status_code,200)
        self.assertEqual(len(self.http.get('/api/incidents/'+own['id']).json()['linked_plans']),2)
        self.login('operator');self.assertEqual(len(self.http.get('/api/incidents/'+own['id']).json()['linked_plans']),1)
        self.login('auditor');self.assertEqual(self.link(own).status_code,403)
        self.login('admin');self.assertEqual(self.post('/api/incidents/'+incident['id']+'/maintenance-plan',{'expected_revision':1,'proposal':'A synthetic proposal with enough text.'},csrf=False).status_code,403)

    def test_source_snapshot_stays_fixed_and_asset_cannot_be_reassigned(self):
        incident=self.create();data=self.link(incident).json();plan=data['request'];captured=data['source_incident']['snapshot']
        self.action(incident,'acknowledge')
        latest=self.http.get('/api/maintenance-requests/'+plan['id']).json()
        self.assertTrue(latest['source_incident']['changed_since_capture'])
        self.assertEqual(latest['source_incident']['snapshot'],captured)
        headers={'x-edgeops-csrf':self.http.cookies.get('edgeops_csrf')}
        self.assertEqual(self.http.put('/api/maintenance-requests/'+plan['id'],headers=headers,json=self.fields(plan,asset_id='PMP-004')).status_code,409)
        changed=self.http.put('/api/maintenance-requests/'+plan['id'],headers=headers,json=self.fields(plan,proposal='An updated synthetic inspection proposal with preserved source context.'))
        self.assertEqual(changed.status_code,200)
        self.assertEqual(changed.json()['source_incident']['snapshot'],captured)

    def test_linked_plan_uses_independent_review_and_never_resolves_source(self):
        self.login('operator');incident=self.create();plan=self.link(incident).json()['request']
        submitted=self.post('/api/maintenance-requests/'+plan['id']+'/actions',{'expected_revision':1,'action':'submit','note':'Submit the synthetic linked plan for independent review.'}).json()['request']
        self.login('admin');approved=self.post('/api/maintenance-requests/'+plan['id']+'/actions',{'expected_revision':submitted['revision'],'action':'approve','note':'Reviewed the frozen synthetic context and proposed inspection.'})
        self.assertEqual(approved.status_code,200)
        self.assertEqual(approved.json()['request']['status'],'approved')
        self.assertEqual(self.http.get('/api/incidents/'+incident['id']).json()['incident']['state'],'open')

    def test_link_audit_failure_rolls_back_plan_link_and_both_audit_events(self):
        incident=self.create()
        with self.server.database() as db:
            db.execute("CREATE TRIGGER deny_link_audit BEFORE INSERT ON audit WHEN NEW.action='synthetic_incident_plan_linked' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.link(incident)
        with self.server.database() as db:
            for table in ('incident_plan_links','maintenance_requests','maintenance_request_events'):
                self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
            self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE action='maintenance_planning_created'").fetchone()[0],0)

    def test_backup_restores_link_snapshot_and_source_context(self):
        incident=self.create();plan=self.link(incident).json()['request']
        backup=Path(self.temp.name)/'backup';restored=Path(self.temp.name)/'restore'
        recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restored)
        with closing(sqlite3.connect(restored/'dashboard.sqlite3')) as db:
            db.row_factory=sqlite3.Row
            self.assertEqual(incidents.plan_source(db,plan['id'],{'role':'admin','id':1})['snapshot']['title'],incident['title'])

    def test_strict_payload_and_capacity_are_enforced(self):
        incident=self.create()
        for changes in ({'expected_revision':True},{'proposal':'   '},{'source_type':'measured'}):
            self.assertEqual(self.link(incident,**changes).status_code,422)
        with patch.object(incidents,'MAX_LINKS_PER_INCIDENT',0):
            self.assertEqual(self.link(incident).status_code,409)
