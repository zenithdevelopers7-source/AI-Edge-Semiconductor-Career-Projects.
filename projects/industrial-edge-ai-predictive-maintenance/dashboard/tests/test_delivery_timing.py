"""Saved service-clock queue deadlines; no worker or eligibility inference."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from edge_delivery import Spool,SpoolReadError
from test_delivery import envelope
import test_acquisition_registry as fixtures


class DeliveryTimingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='edgeops-delivery-timing-');self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'spool.sqlite3';self.spool=Spool(self.path)
        with patch('edge_delivery.time.time',return_value=1700000000.125):self.key=self.spool.enqueue(envelope())['event_key']

    def test_queue_creation_and_pending_deadline_use_saved_utc_without_device_time_substitution(self):
        row=self.spool.status()['records'][0]
        for key in ('queued_at_utc','updated_at_utc','retry_not_before_utc'):self.assertEqual(row[key],'2023-11-14T22:13:20.125000+00:00')
        self.assertIsNone(row['lease_expires_at_utc'])
        self.assertNotEqual(row['queued_at_utc'],envelope()['observation']['timestamp']['gateway_received_utc'])
        self.assertEqual(Spool(self.path).status()['records'],[row])

    def test_claim_and_transient_backoff_expose_only_applicable_saved_deadlines(self):
        with patch('edge_delivery.time.time',return_value=1700000001.125):claim=self.spool.claim()
        inflight=self.spool.status()['records'][0]
        self.assertEqual(inflight['lease_expires_at_utc'],'2023-11-14T22:14:06.125000+00:00');self.assertIsNone(inflight['retry_not_before_utc'])
        self.assertEqual(inflight['updated_at_utc'],'2023-11-14T22:13:21.125000+00:00')
        with patch('edge_delivery.time.time',return_value=1700000002.125):self.spool.finish(claim,error='transport-unavailable')
        pending=self.spool.status()['records'][0]
        self.assertEqual(pending['retry_not_before_utc'],'2023-11-14T22:13:24.125000+00:00');self.assertIsNone(pending['lease_expires_at_utc'])
        self.assertEqual(pending['updated_at_utc'],'2023-11-14T22:13:22.125000+00:00')

    def test_delivered_and_blocked_do_not_advertise_internal_next_at_as_scheduled_retry(self):
        for state in ('delivered','blocked'):
            path=Path(self.temp.name)/(state+'.sqlite3');spool=Spool(path)
            with patch('edge_delivery.time.time',return_value=1700000000.125):spool.enqueue(envelope())
            with patch('edge_delivery.time.time',return_value=1700000001.125):claim=spool.claim()
            receipt={'tier':'central-committed','event_key':claim['event_key'],'content_hash':claim['content_hash'],'receipt_id':'test-only','committed_at':'2020-01-01T00:00:00Z'}
            with patch('edge_delivery.time.time',return_value=1700000003.125):
                if state=='delivered':spool.finish(claim,receipt=receipt)
                else:spool.finish(claim,error='http-403',permanent=True)
            row=spool.status()['records'][0]
            self.assertEqual(row['state'],state);self.assertIsNone(row['retry_not_before_utc']);self.assertIsNone(row['lease_expires_at_utc'])
            self.assertEqual(row['updated_at_utc'],'2023-11-14T22:13:23.125000+00:00')
            if state=='delivered':self.assertNotEqual(json.loads(row['receipt'])['committed_at'],row['updated_at_utc'])

    def test_unsupported_selected_timing_refuses_partial_read_without_mutation(self):
        for field,value in [('created_at','not-a-time'),('updated_at',-1),('next_at',1e100)]:
            with self.spool.db() as db:
                original=db.execute('SELECT '+field+' FROM delivery_spool').fetchone()[0]
                db.execute('UPDATE delivery_spool SET '+field+'=?',(value,))
                before=[tuple(row) for row in db.execute('SELECT * FROM delivery_spool')]
            with self.subTest(field=field),self.assertRaises(SpoolReadError):self.spool.status()
            with self.spool.db() as db:
                self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM delivery_spool')],before)
                db.execute('UPDATE delivery_spool SET '+field+'=?',(original,))
        with self.spool.db() as db:db.execute("UPDATE delivery_spool SET state='inflight',lease_until=NULL")
        with self.assertRaises(SpoolReadError):self.spool.status()


class DeliveryTimingApiTests(unittest.TestCase):
    login=fixtures.AcquisitionRegistryApiTests.login
    def setUp(self):
        fixtures.AcquisitionRegistryApiTests.setUp(self)
        self.path=Path(self.temp.name)/'timing-spool.sqlite3'
        env=patch.dict(os.environ,{'EDGEOPS_DELIVERY_SPOOL_DB':str(self.path)});env.start();self.addCleanup(env.stop)
        self.spool=Spool(self.path)
        for sequence in range(2):
            sample=envelope();sample['observation']['sequence']=sequence;self.spool.enqueue(sample)
        self.spool.claim()

    def test_roles_read_paged_and_filtered_timing_without_tokens_or_queue_mutation(self):
        with self.spool.db() as db:before=[tuple(row) for row in db.execute('SELECT * FROM delivery_spool ORDER BY event_key')]
        for role in ('admin','operator','auditor'):
            self.login(role)
            for state in ('','pending','inflight'):
                response=self.http.get('/api/acquisition/delivery',params={'state':state,'limit':1});self.assertEqual(response.status_code,200)
                row=response.json()['records'][0]
                self.assertTrue(row['queued_at_utc'].endswith('+00:00'));self.assertTrue(row['updated_at_utc'].endswith('+00:00'))
                self.assertNotIn('lease_token',row);self.assertNotIn('payload',row);self.assertNotIn('actor',row)
        self.http.cookies.clear();self.assertEqual(self.http.get('/api/acquisition/delivery').status_code,401)
        with self.spool.db() as db:self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM delivery_spool ORDER BY event_key')],before)

    def test_corrupt_timing_returns_safe_service_failure_instead_of_partial_page_or_client_error(self):
        with self.spool.db() as db:db.execute("UPDATE delivery_spool SET next_at='private-invalid-timing' WHERE state='pending'")
        response=self.http.get('/api/acquisition/delivery')
        self.assertEqual(response.status_code,503);self.assertEqual(response.json(),{'detail':'Saved delivery timing is unavailable or inconsistent'})
        self.assertNotIn('private-invalid-timing',response.text);self.assertNotIn('records',response.json())
        self.assertEqual(self.http.get('/api/acquisition/delivery',params={'before':'invalid!'}).status_code,422)
