"""Explicit persisted synthetic observation-to-incident traceability."""
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
from test_delivery import envelope


class ObservationIncidentTests(unittest.TestCase):
    login=fixture.AcquisitionRegistryApiTests.login
    post=fixture.AcquisitionRegistryApiTests.post

    def setUp(self):
        fixture.AcquisitionRegistryApiTests.setUp(self)
        binding=fixture.binding();binding['asset_id']='MTR-001'
        self.assertEqual(self.post('/api/acquisition-bindings',binding).status_code,201)
        self.source=self.ingest()

    def ingest(self,sequence=0,asset='MTR-001',device='test-device'):
        body=envelope();body['observation']['asset_id']=asset;body['observation']['sequence']=sequence
        body['observation']['device_id']=device
        response=self.post('/api/acquisition/ingest',body);self.assertEqual(response.status_code,201,response.text)
        return response.json()

    def body(self,source=None,**changes):
        source=source or self.source
        return {'request_key':secrets.token_hex(16),'event_key':source['event_key'],'content_hash':source['content_hash'],
                'title':'Review this saved synthetic observation','observation':'Explicit synthetic interpretation; no equipment fault is established.',
                'severity':'watch',**changes}

    def create(self,body=None):return self.post('/api/incidents/from-observation',body or self.body())

    def test_captures_all_readings_quality_times_units_and_exact_asset(self):
        result=self.create();self.assertEqual(result.status_code,200,result.text);data=result.json();source=data['source_observation']
        self.assertEqual(data['incident']['asset_id'],'MTR-001');self.assertEqual(data['incident']['state'],'open')
        self.assertEqual(source['observation']['measurements']['acceleration_x_mps2'],0)
        self.assertIsNone(source['observation']['measurements']['current_a']);self.assertEqual(source['channels']['current_a']['unit'],'A')
        self.assertEqual(source['observation']['timestamp']['clock_quality'],'gateway_receipt_only')
        self.assertIsNone(source['observation']['timestamp']['device_time_utc'])
        self.assertEqual(source['receipt_id'],self.source['receipt_id']);self.assertEqual(source['content_hash'],self.source['content_hash'])
        self.assertNotIn('freshness',source);self.assertNotIn('central_age_seconds',source)
        self.assertFalse(data['automatic_detection']);self.assertFalse(data['equipment_authorized']);self.assertFalse(data['hardware_connected'])
        self.server.init_db();self.assertEqual(self.http.get('/api/incidents/'+data['incident']['id']).json()['source_observation'],source)

    def test_exact_concurrent_retry_and_one_incident_per_creator_observation(self):
        body=self.body()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.create(body),range(2)))
        self.assertTrue(all(r.status_code==200 for r in results));self.assertEqual(sorted(r.json()['created'] for r in results),[False,True])
        self.assertEqual(self.create().status_code,409)
        self.assertEqual(self.create({**body,'title':'Changed title cannot reuse the same key'}).status_code,409)
        self.login('operator');other=self.create();self.assertEqual(other.status_code,200)
        self.assertNotEqual(other.json()['incident']['id'],results[0].json()['incident']['id'])

    def test_unknown_changed_or_corrupt_source_rejects_without_partial_incident(self):
        self.assertEqual(self.create(self.body(event_key='f'*64)).status_code,404)
        self.assertEqual(self.create(self.body(content_hash='f'*64)).status_code,409)
        with self.server.database() as db:
            source=db.execute('SELECT payload FROM acquisition_observations').fetchone()[0];body=json.loads(source)
            body['observation']['measurements']['acceleration_x_mps2']=999
            db.execute('UPDATE acquisition_observations SET payload=?',(json.dumps(body),))
        self.assertEqual(self.create().status_code,503)
        self.assertEqual(self.http.get('/api/incidents').json()['total'],0)

    def test_unknown_asset_or_mismatching_binding_is_not_inferred(self):
        with self.server.database() as db:db.execute("UPDATE acquisition_bindings SET asset_id='other-asset'")
        self.assertEqual(self.create().status_code,503)
        with self.server.database() as db:db.execute("UPDATE acquisition_bindings SET asset_id='MTR-001',definition='corrupt'")
        self.assertEqual(self.create().status_code,503)
        binding=fixture.binding('other-device');self.assertEqual(self.post('/api/acquisition-bindings',binding).status_code,201)
        other=self.ingest(1,'test-asset','other-device');self.assertEqual(self.create(self.body(other)).status_code,422)
        page=self.http.get('/api/acquisition/observations?device_id=other-device')
        self.assertEqual(page.status_code,200);self.assertFalse(page.json()['incident_asset_matches'])

    def test_retired_binding_can_supply_historical_context_without_live_claim(self):
        self.assertEqual(self.post('/api/acquisition-bindings/test-device/retire',{'expected_revision':1}).status_code,200)
        data=self.create().json();self.assertEqual(data['source_observation']['binding_at_capture']['status'],'retired')
        self.assertEqual(data['source_observation']['binding_revision'],1)
        self.assertEqual(data['source_observation']['binding_at_capture']['revision'],2)
        self.assertFalse(data['hardware_connected'])

    def test_roles_csrf_and_current_session_are_rechecked(self):
        self.assertEqual(self.post('/api/incidents/from-observation',self.body(),csrf=False).status_code,403)
        self.login('auditor');self.assertEqual(self.create().status_code,403)
        self.assertFalse(self.http.get('/api/acquisition/observations?device_id=test-device').json()['can_prepare_incident'])
        self.http.cookies.clear();self.assertEqual(self.http.post('/api/incidents/from-observation',json=self.body()).status_code,401)
        self.login('admin');original=incidents.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(incidents,'fresh_actor',side_effect=revoke):self.assertEqual(self.create().status_code,401)

    def test_strict_payload_and_capacity_keep_original_observation(self):
        for changes in ({'source_type':'measured'},{'asset_id':'PMP-004'},{'severity':'emergency'},{'event_key':True},
                        {'title':'tiny'},{'observation':'short'},{'content_hash':'bad'}):
            self.assertEqual(self.create(self.body(**changes)).status_code,422,str(changes))
        with patch.object(incidents,'MAX_INCIDENTS',0):self.assertEqual(self.create().status_code,409)
        with self.server.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM acquisition_observations').fetchone()[0],1)

    def test_audit_or_source_link_failure_rolls_back_all_domain_records(self):
        for table,condition in [('audit',"WHEN NEW.action='synthetic_incident_observation_linked'"),('incident_observation_sources','')]:
            with self.server.database() as db:db.execute('CREATE TRIGGER fail_source BEFORE INSERT ON '+table+' '+condition+" BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END")
            with self.assertRaises(sqlite3.IntegrityError):self.create()
            with self.server.database() as db:
                for name in ('synthetic_incidents','synthetic_incident_events','incident_observation_sources'):
                    self.assertEqual(db.execute('SELECT count(*) FROM '+name).fetchone()[0],0)
                self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE action LIKE 'synthetic_incident_%'").fetchone()[0],0)
                db.execute('DROP TRIGGER fail_source')

    def test_snapshot_survives_new_readings_source_corruption_and_plan_capture(self):
        body=self.body();data=self.create(body).json();row=data['incident'];self.ingest(1)
        with self.server.database() as db:db.execute("UPDATE acquisition_observations SET payload='corrupt' WHERE event_key=?",(self.source['event_key'],))
        retained=self.http.get('/api/incidents/'+row['id']).json();self.assertEqual(retained['source_observation'],data['source_observation'])
        self.assertFalse(self.create(body).json()['created']) # Exact retry uses the saved capture, not mutable live history.
        plan=self.post('/api/incidents/'+row['id']+'/maintenance-plan',{'expected_revision':1,'proposal':'Inspect the retained synthetic source context from the saved observation.'}).json()
        self.assertEqual(plan['source_incident']['snapshot']['source_observation'],data['source_observation'])
        self.login('operator');self.assertEqual(self.http.get('/api/incidents/'+row['id']).status_code,404)

    def test_backup_restore_retains_source_identity_and_observation(self):
        data=self.create().json();backup=Path(self.temp.name)/'backup';restore=Path(self.temp.name)/'restore'
        recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restore)
        with closing(sqlite3.connect(restore/'dashboard.sqlite3')) as db:
            self.assertEqual(json.loads(db.execute('SELECT snapshot_json FROM incident_observation_sources').fetchone()[0]),data['source_observation'])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertEqual(db.execute('SELECT event_key FROM acquisition_observations').fetchone()[0],self.source['event_key'])
