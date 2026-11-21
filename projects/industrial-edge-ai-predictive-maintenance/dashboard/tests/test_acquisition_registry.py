"""Synthetic registry identity, contract, revocation and persistence tests."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError
from acquisition_registry import Observation


def binding(device='test-device'):
    return {'site_id':'test-site','asset_id':'test-asset','device_id':device,
            'source_type':'synthetic','transport':'simulator','firmware_ref':'test configuration only',
            'configuration_sha256':'1'*64}


def observation(device='test-device'):
    return {'schema_version':'2.0','event_type':'telemetry.sample','source_type':'synthetic',
            'site_id':'test-site','asset_id':'test-asset','device_id':device,'boot_id':None,'sequence':0,
            'timestamp':{'device_uptime_ms':0,'device_time_utc':None,'gateway_received_utc':'2026-11-19T10:00:00Z','clock_quality':'gateway_receipt_only'},
            'measurements':{'acceleration_x_mps2':0,'acceleration_y_mps2':0,'acceleration_z_mps2':0,'motor_case_temperature_c':None,'bus_voltage_v':None,'current_a':None},
            'quality':{'adxl345':'valid','ds18b20':'not_connected','ina219':'not_connected','calibration':'unknown','session_quality':'unavailable'}}


class ObservationContractTests(unittest.TestCase):
    def test_zero_partial_channels_and_si_units_are_preserved(self):
        result=Observation.model_validate(observation())
        self.assertEqual(result.measurements.acceleration_x_mps2,0)
        self.assertIsNone(result.measurements.current_a)

    def test_unknown_fields_sources_versions_bool_coercion_and_nonfinite_are_rejected(self):
        for key,value in [('sequence',True),('sequence',-1),('sequence',4294967296),('source_type','measured'),('source_type','replayed'),('schema_version','3.0'),('motor_command','run')]:
            data=observation();data[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValidationError):Observation.model_validate(data)
        for value in [True,'0',float('nan'),float('inf')]:
            data=observation();data['measurements']['acceleration_x_mps2']=value
            with self.subTest(value=value),self.assertRaises(ValidationError):Observation.model_validate(data)
        data=observation();data['measurements']['current_ma']=1
        with self.assertRaises(ValidationError):Observation.model_validate(data)

    def test_timestamp_boot_and_quality_ambiguity_are_rejected(self):
        variants=[]
        data=observation();data['timestamp']['gateway_received_utc']='2026-11-19T10:00:00';variants.append(data)
        data=observation();data['timestamp']['gateway_received_utc']=123;variants.append(data)
        data=observation();data['timestamp']['clock_quality']='device_clock_verified';variants.append(data)
        data=observation();data['quality']['adxl345']='invalid';variants.append(data)
        data=observation();data['measurements']['acceleration_x_mps2']=None;variants.append(data)
        data=observation();data['quality']['session_quality']='verified';variants.append(data)
        data=observation();data['boot_id']='invented-boot';variants.append(data)
        for data in variants:
            with self.subTest(data=data),self.assertRaises(ValidationError):Observation.model_validate(data)


class AcquisitionRegistryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='edgeops-binding-');self.addCleanup(self.temp.cleanup)
        self.password=secrets.token_urlsafe(24)
        env=patch.dict(os.environ,{'EDGEOPS_DASHBOARD_DB':str(Path(self.temp.name)/'dashboard.sqlite3'),'EDGEOPS_ADMIN_EMAIL':'admin@example.invalid','EDGEOPS_ADMIN_PASSWORD':self.password})
        env.start();self.addCleanup(env.stop)
        import server
        self.server=importlib.reload(server);self.server.init_db()
        with self.server.database() as db:
            for role in ('operator','auditor'):
                db.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',(role+'@example.invalid',self.server.password_hash(self.password),role))
        self.http=TestClient(self.server.app);self.addCleanup(self.http.close)
        self.login('admin')

    def login(self,role):
        self.http.cookies.clear()
        self.assertEqual(self.http.post('/api/auth/login',json={'email':role+'@example.invalid','password':self.password}).status_code,200)

    def post(self,path,body,csrf=True):
        return self.http.post(path,json=body,headers={'x-edgeops-csrf':self.http.cookies.get('edgeops_csrf')} if csrf else {})

    def test_idempotent_create_conflict_retire_persistence_and_no_fake_enrollment(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _: self.post('/api/acquisition-bindings',binding()).status_code,range(2)))
        self.assertEqual(sorted(results),[200,201])
        self.assertEqual(self.post('/api/acquisition-bindings',binding()).status_code,200)
        changed=binding();changed['site_id']='other-site'
        self.assertEqual(self.post('/api/acquisition-bindings',changed).status_code,409)
        self.server.init_db()
        data=self.http.get('/api/acquisition-bindings').json()
        self.assertEqual(len(data['bindings']),1);self.assertFalse(data['hardware_connected'])
        self.assertEqual(self.post('/api/acquisition/validate',observation()).status_code,200)
        self.assertEqual(self.post('/api/acquisition-bindings/test-device/retire',{'expected_revision':2}).status_code,409)
        self.assertEqual(self.post('/api/acquisition-bindings/test-device/retire',{'expected_revision':1}).status_code,200)
        self.assertEqual(self.post('/api/acquisition/validate',observation()).status_code,403)
        self.assertEqual(self.post('/api/acquisition-bindings',binding()).status_code,409)
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM acquisition_binding_events').fetchone()[0],2)

    def test_csrf_roles_unknown_binding_and_cross_scope_validation(self):
        self.assertEqual(self.post('/api/acquisition-bindings',binding(),False).status_code,403)
        self.assertEqual(self.post('/api/acquisition-bindings',binding()).status_code,201)
        data=observation();data['asset_id']='foreign-asset'
        self.assertEqual(self.post('/api/acquisition/validate',data).status_code,403)
        self.assertEqual(self.post('/api/acquisition/validate',observation('unknown')).status_code,403)
        self.login('operator')
        self.assertEqual(self.post('/api/acquisition-bindings',binding('denied')).status_code,403)
        self.assertEqual(self.post('/api/acquisition/validate',observation()).status_code,200)
        self.login('auditor')
        self.assertEqual(self.http.get('/api/acquisition-bindings').status_code,200)
        self.assertEqual(self.post('/api/acquisition/validate',observation()).status_code,403)

    def test_schema_pagination_and_validation_never_persists_observations(self):
        for device in ('a','b','c'):self.assertEqual(self.post('/api/acquisition-bindings',binding(device)).status_code,201)
        first=self.http.get('/api/acquisition-bindings?limit=2').json()
        second=self.http.get('/api/acquisition-bindings?limit=2&after='+first['next_after']).json()
        self.assertEqual([r['device_id'] for r in first['bindings']+second['bindings']],['a','b','c'])
        self.assertFalse(self.http.get('/api/acquisition-contract').json()['schema']['additionalProperties'])
        self.assertFalse(self.post('/api/acquisition/validate',observation('a')).json()['observation_persisted'])
        bad=observation('a');bad['measurements']['acceleration_x_mps2']=float('nan')
        response=self.http.post('/api/acquisition/validate',content=json.dumps(bad),headers={'content-type':'application/json','x-edgeops-csrf':self.http.cookies.get('edgeops_csrf')})
        self.assertEqual(response.status_code,422)
        self.assertNotIn('input',response.json()['detail'][0])

    def test_current_role_rechecked_under_transaction(self):
        # Routes retain the original callable, so simulate revocation after its result is read.
        from acquisition_registry import fresh_actor
        def revoke(db,current):
            db.execute("UPDATE users SET role='operator' WHERE id=?",(current['id'],))
            return fresh_actor(db,current)
        with patch('acquisition_registry.fresh_actor',side_effect=revoke):
            self.assertEqual(self.post('/api/acquisition-bindings',binding()).status_code,403)
        self.assertEqual(self.http.get('/api/acquisition-bindings').json()['bindings'],[])
