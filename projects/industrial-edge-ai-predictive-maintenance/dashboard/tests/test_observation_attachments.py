"""Scoped, revisioned observation evidence; no live hardware operations."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import secrets
import sqlite3
import unittest
from unittest.mock import patch

import incidents
import recovery
import test_acquisition_registry as fixture
import test_incidents as cases
import test_observation_incidents as source_cases
from test_delivery import envelope


class ObservationAttachmentTests(unittest.TestCase):
    setUp=source_cases.ObservationIncidentTests.setUp
    login=fixture.AcquisitionRegistryApiTests.login
    post=fixture.AcquisitionRegistryApiTests.post
    ingest=source_cases.ObservationIncidentTests.ingest
    source_body=source_cases.ObservationIncidentTests.body
    action=cases.IncidentApiTests.action
    manual=cases.IncidentApiTests.create

    def case(self):
        result=self.post('/api/incidents/from-observation',self.source_body());self.assertEqual(result.status_code,200,result.text)
        return result.json()['incident']

    def body(self,row,source,**changes):
        return {'request_key':secrets.token_hex(16),'expected_revision':row['revision'],'event_key':source['event_key'],
                'content_hash':source['content_hash'],'note':'Attach this later synthetic observation to the ongoing investigation.',**changes}

    def save(self,row,body):return self.post('/api/incidents/'+row['id']+'/observations',body)

    def alternate(self,device,site,asset='MTR-001'):
        binding=fixture.binding(device);binding.update(site_id=site,asset_id=asset)
        self.assertEqual(self.post('/api/acquisition-bindings',binding).status_code,201)
        data=envelope();data['observation'].update(device_id=device,site_id=site,asset_id=asset)
        response=self.post('/api/acquisition/ingest',data);self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def test_preserves_initial_context_state_and_captures_history(self):
        row=self.case();source=self.ingest(1);result=self.save(row,self.body(row,source));self.assertEqual(result.status_code,200,result.text)
        data=result.json();self.assertEqual(data['incident']['state'],'open');self.assertEqual(data['incident']['revision'],2)
        self.assertEqual(data['source_observation']['event_key'],self.source['event_key'])
        captured=data['history'][0]['attached_observation'];self.assertEqual(captured['content_hash'],source['content_hash'])
        self.assertEqual(captured['observation']['measurements']['acceleration_x_mps2'],0)
        self.assertIsNone(captured['observation']['measurements']['current_a']);self.assertNotIn('freshness',captured)
        self.assertFalse(data['hardware_connected']);self.assertFalse(data['equipment_authorized'])
        self.server.init_db();self.assertEqual(self.http.get('/api/incidents/'+row['id']).json()['attached_observations'][0]['snapshot'],captured)
        new=data['incident'];self.assertEqual(self.save(new,self.body(new,source)).status_code,409)
        self.assertEqual(self.save(new,self.body(new,self.source)).status_code,409)

    def test_exact_concurrent_retry_and_rejected_changed_key(self):
        row=self.case();body=self.body(row,self.ingest(1))
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.save(row,body),range(2)))
        self.assertTrue(all(r.status_code==200 for r in results));self.assertEqual(sorted(r.json()['created'] for r in results),[False,True])
        current=results[0].json()['incident'];current=self.action(current,'acknowledge').json()['incident'];current=self.action(current,'resolve').json()['incident']
        retry=self.save(current,body);self.assertEqual(retry.status_code,200);self.assertFalse(retry.json()['created']);self.assertEqual(retry.json()['attachment_revision'],2)
        self.assertEqual(self.save(current,{**body,'note':'Changed content must never reuse a committed attachment key.'}).status_code,409)

    def test_distinct_concurrent_sources_cannot_overwrite_revision(self):
        row=self.case();bodies=[self.body(row,self.ingest(1)),self.body(row,self.ingest(2))]
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda body:self.save(row,body),bodies))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        self.assertEqual(len(self.http.get('/api/incidents/'+row['id']).json()['attached_observations']),1)

    def test_exact_asset_site_and_first_attachment_context(self):
        row=self.case();wrong_asset=self.alternate('wrong-asset','test-site','PMP-004');wrong_site=self.alternate('wrong-site','another-site')
        self.assertEqual(self.save(row,self.body(row,wrong_asset)).status_code,422)
        self.assertEqual(self.save(row,self.body(row,wrong_site)).status_code,422)
        manual=self.manual();data=self.save(manual,self.body(manual,wrong_site)).json();self.assertEqual(data['incident']['revision'],2)
        self.assertEqual(self.save(data['incident'],self.body(data['incident'],self.source)).status_code,422)

    def test_assignee_access_readonly_roles_and_reassignment_revocation(self):
        row=self.case();source=self.ingest(1);self.login('operator');self.assertEqual(self.save(row,self.body(row,source)).status_code,404)
        self.login('admin')
        with self.server.database() as db:target=db.execute("SELECT id FROM users WHERE role='operator'").fetchone()[0]
        row=self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':1,'assignee_id':target,'note':'Share synthetic observation evidence with this operator.'}).json()['incident']
        self.login('operator');body=self.body(row,source);result=self.save(row,body);self.assertEqual(result.status_code,200);row=result.json()['incident']
        self.login('admin');row=self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':row['revision'],'assignee_id':None,'note':'Remove the temporary synthetic evidence assignment.'}).json()['incident']
        self.login('operator');self.assertEqual(self.save(row,body).status_code,404)
        self.login('auditor');data=self.http.get('/api/incidents/'+row['id']).json();self.assertFalse(data['can_attach_observation']);self.assertEqual(self.save(row,body).status_code,403)
        self.http.cookies.clear();self.assertEqual(self.http.post('/api/incidents/'+row['id']+'/observations',json=body).status_code,401)

    def test_strict_inputs_csrf_and_session_recheck(self):
        row=self.case();source=self.ingest(1);body=self.body(row,source)
        for changes in ({'expected_revision':True},{'event_key':'bad'},{'content_hash':False},{'note':'short'},{'note':'x'*801},{'source_type':'measured'}):
            self.assertEqual(self.save(row,{**body,**changes}).status_code,422)
        self.assertEqual(self.post('/api/incidents/'+row['id']+'/observations',body,csrf=False).status_code,403)
        original=incidents.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(incidents,'fresh_actor',side_effect=revoke):self.assertEqual(self.save(row,body).status_code,401)

    def test_state_capacity_and_source_integrity_guards(self):
        row=self.case();source=self.ingest(1);body=self.body(row,source)
        with patch.object(incidents,'MAX_ATTACHED_OBSERVATIONS',0):self.assertEqual(self.save(row,body).status_code,409)
        with patch.object(incidents,'MAX_REVISIONS',1):self.assertEqual(self.save(row,body).status_code,409)
        self.assertEqual(self.save(row,{**body,'event_key':'f'*64}).status_code,404)
        self.assertEqual(self.save(row,{**body,'content_hash':'f'*64}).status_code,409)
        with self.server.database() as db:db.execute("UPDATE acquisition_observations SET payload='corrupt' WHERE event_key=?",(source['event_key'],))
        self.assertEqual(self.save(row,body).status_code,503)
        row=self.action(row,'acknowledge').json()['incident'];row=self.action(row,'resolve').json()['incident']
        self.assertEqual(self.save(row,self.body(row,source)).status_code,409)

    def test_audit_or_attachment_failure_rolls_back_revision_and_history(self):
        row=self.case();body=self.body(row,self.ingest(1))
        for table,condition in [('audit',"WHEN NEW.action='synthetic_incident_observation_attached'"),('incident_observation_attachments','')]:
            with self.server.database() as db:db.execute('CREATE TRIGGER fail_attach BEFORE INSERT ON '+table+' '+condition+" BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END")
            with self.assertRaises(sqlite3.IntegrityError):self.save(row,body)
            data=self.http.get('/api/incidents/'+row['id']).json();self.assertEqual(data['incident']['revision'],1);self.assertEqual(len(data['history']),1);self.assertEqual(data['attached_observations'],[])
            with self.server.database() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE action='synthetic_incident_observation_attached'").fetchone()[0],0)
                db.execute('DROP TRIGGER fail_attach')

    def test_retired_context_and_frozen_plan_capture_are_preserved(self):
        row=self.case();source=self.ingest(1);later=self.ingest(2)
        self.assertEqual(self.post('/api/acquisition-bindings/test-device/retire',{'expected_revision':1}).status_code,200)
        data=self.save(row,self.body(row,source)).json();row=data['incident'];self.assertEqual(data['attached_observations'][0]['snapshot']['binding_at_capture']['status'],'retired')
        plan=self.post('/api/incidents/'+row['id']+'/maintenance-plan',{'expected_revision':row['revision'],'proposal':'Inspect the retained sequence of synthetic observation evidence.'}).json()['request']
        self.assertEqual(self.save(row,self.body(row,later)).status_code,200)
        captured=self.http.get('/api/maintenance-requests/'+plan['id']).json()['source_incident']
        self.assertTrue(captured['changed_since_capture']);self.assertEqual(len(captured['snapshot']['attached_observations']),1)

    def test_backup_restore_and_source_corruption_do_not_rewrite_capture(self):
        row=self.case();source=self.ingest(1);body=self.body(row,source);data=self.save(row,body).json()
        with self.server.database() as db:db.execute("UPDATE acquisition_observations SET payload='corrupt' WHERE event_key=?",(source['event_key'],))
        self.assertEqual(self.http.get('/api/incidents/'+row['id']).json()['attached_observations'],data['attached_observations'])
        self.assertFalse(self.save(row,body).json()['created'])
        backup=Path(self.temp.name)/'backup';restore=Path(self.temp.name)/'restore';recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restore)
        with closing(sqlite3.connect(restore/'dashboard.sqlite3')) as db:
            self.assertEqual(json.loads(db.execute('SELECT snapshot_json FROM incident_observation_attachments').fetchone()[0]),data['attached_observations'][0]['snapshot'])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
