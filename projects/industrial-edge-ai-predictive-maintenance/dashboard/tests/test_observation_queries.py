"""Persisted query pagination, provenance, integrity and age semantics."""
from datetime import datetime,timedelta,timezone
import json
import unittest

import test_acquisition_registry as fixtures
from test_delivery import envelope


class ObservationQueryTests(unittest.TestCase):
    login=fixtures.AcquisitionRegistryApiTests.login
    post=fixtures.AcquisitionRegistryApiTests.post

    def setUp(self):
        fixtures.AcquisitionRegistryApiTests.setUp(self)
        self.assertEqual(self.post('/api/acquisition-bindings',fixtures.binding()).status_code,201)

    def ingest(self,sequence=0,age=None,value=0):
        data=envelope();data['observation']['sequence']=sequence
        data['observation']['measurements']['acceleration_x_mps2']=value
        if age is not None:
            data['observation']['timestamp']['device_time_utc']=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat()
            data['observation']['timestamp']['clock_quality']='device_clock_verified'
        result=self.post('/api/acquisition/ingest',data)
        self.assertEqual(result.status_code,201,result.text)
        return result.json()

    def query(self,suffix=''):
        return self.http.get('/api/acquisition/observations?device_id=test-device'+suffix)

    def test_persisted_zero_null_units_and_unverified_clock(self):
        self.ingest()
        data=self.query().json();row=data['records'][0]
        self.assertEqual(row['observation']['measurements']['acceleration_x_mps2'],0)
        self.assertIsNone(row['observation']['measurements']['current_a'])
        self.assertEqual(data['channels']['acceleration_x_mps2']['unit'],'m/s²')
        self.assertEqual(row['freshness']['state'],'clock-unverified')
        self.assertIsNone(row['freshness']['observed_at'])
        self.assertFalse(data['hardware_connected']);self.assertEqual(data['device_health'],'not-established')

    def test_recent_central_receipt_does_not_hide_old_observation_or_future_clock(self):
        self.ingest(0,age=3600)
        row=self.query().json()['records'][0]
        self.assertEqual(row['freshness']['state'],'stale')
        self.assertLess(row['central_age_seconds'],20)
        self.ingest(1,age=-3600)
        self.assertEqual(self.query().json()['records'][0]['freshness']['state'],'future-time')
        self.ingest(2,age=10)
        self.assertEqual(self.query().json()['records'][0]['freshness']['state'],'within-display-age')
        self.assertEqual(self.query('&max_age_seconds=1').json()['records'][0]['freshness']['state'],'stale')

    def test_stable_pagination_with_identical_commit_times_and_new_arrival(self):
        for sequence in range(5):self.ingest(sequence)
        with self.server.database() as db:db.execute("UPDATE acquisition_observations SET committed_at='2026-11-19T10:00:00+00:00'")
        found=[];before=''
        first=self.query('&limit=2').json();found.extend(r['event_key'] for r in first['records']);before=first['next_before']
        self.ingest(9)
        while before:
            page=self.query('&limit=2&before='+before).json();found.extend(r['event_key'] for r in page['records']);before=page['next_before']
        self.assertEqual(len(found),5);self.assertEqual(len(set(found)),5)
        self.assertEqual(self.query('&limit=101').status_code,422)
        self.assertEqual(self.query('&before=invalid-cursor').status_code,422)

    def test_auth_roles_unknown_binding_and_retired_history(self):
        self.ingest()
        self.post('/api/acquisition-bindings/test-device/retire',{'expected_revision':1})
        self.assertEqual(self.query().json()['binding_status'],'retired')
        for role in ('operator','auditor'):
            self.login(role);self.assertEqual(self.query().status_code,200)
        self.http.cookies.clear();self.assertEqual(self.query().status_code,401)
        self.login('admin')
        self.assertEqual(self.http.get('/api/acquisition/observations?device_id=unknown').status_code,404)
        self.assertEqual(self.query('&max_age_seconds=0').status_code,422)

    def test_corrupt_payload_is_not_returned_as_valid_history(self):
        self.ingest()
        with self.server.database() as db:
            row=db.execute('SELECT event_key,payload FROM acquisition_observations').fetchone()
            data=json.loads(row['payload']);data['observation']['measurements']['acceleration_x_mps2']=999
            db.execute('UPDATE acquisition_observations SET payload=? WHERE event_key=?',(json.dumps(data),row['event_key']))
        response=self.query();self.assertEqual(response.status_code,503)
        self.assertNotIn('records',response.json())
