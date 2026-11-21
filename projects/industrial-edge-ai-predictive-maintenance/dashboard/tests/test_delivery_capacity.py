"""Retained-row and serialized-payload accounting; reads never reclaim capacity."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from edge_delivery import Spool
from test_delivery import envelope
import test_acquisition_registry as fixtures


class DeliveryCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='edgeops-delivery-capacity-');self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'spool.sqlite3';self.spool=Spool(self.path)

    def enqueue(self,sequence):
        data=envelope();data['observation']['sequence']=sequence
        return self.spool.enqueue(data)

    def test_empty_capacity_and_stored_utf8_byte_accounting(self):
        self.assertEqual(self.spool.status()['usage'],{'records':0,'payload_bytes':0})
        self.enqueue(0);self.enqueue(1)
        with self.spool.db() as db:
            # Deliberate storage-only fixture: accounting measures bytes, not character count.
            db.execute('UPDATE delivery_spool SET payload=? WHERE event_key=(SELECT MIN(event_key) FROM delivery_spool)',('é温',))
            payloads=[row[0] for row in db.execute('SELECT payload FROM delivery_spool')]
        expected=sum(len(value.encode('utf-8')) for value in payloads)
        self.assertEqual(self.spool.status()['usage'],{'records':2,'payload_bytes':expected})
        self.assertNotEqual(expected,sum(len(value) for value in payloads))

    def test_delivered_and_blocked_rows_remain_in_global_usage_across_filters_and_pages(self):
        for sequence in range(3):self.enqueue(sequence)
        before=self.spool.status()['usage']
        claim=self.spool.claim()
        self.spool.finish(claim,receipt={'tier':'central-committed','event_key':claim['event_key'],'content_hash':claim['content_hash'],'receipt_id':'test-receipt'})
        self.spool.finish(self.spool.claim(),error='http-403',permanent=True)
        for state in ('','pending','inflight','delivered','blocked'):
            data=self.spool.status(state=state,limit=1)
            self.assertEqual(data['usage'],before);self.assertEqual(sum(data['counts'].values()),3)
        first=self.spool.status(limit=1)
        self.assertEqual(self.spool.status(before=first['page']['next_before'],limit=1)['usage'],before)

    def test_identical_retry_and_capacity_rejection_do_not_increase_usage(self):
        self.enqueue(0);before=self.spool.status()['usage']
        capped=Spool(self.path,max_rows=1)
        self.assertFalse(capped.enqueue(envelope())['created'])
        sample=envelope();sample['observation']['sequence']=1
        with self.assertRaises(OverflowError):capped.enqueue(sample)
        self.assertEqual(capped.status()['usage'],before)
        self.assertEqual(capped.status()['limits']['records'],1)

    def test_exact_payload_limit_and_reduced_profile_preserve_reported_usage(self):
        self.enqueue(0);before=self.spool.status()['usage']
        exact=Spool(self.path,max_bytes=before['payload_bytes'])
        self.assertFalse(exact.enqueue(envelope())['created'])
        sample=envelope();sample['observation']['sequence']=1
        with self.assertRaises(OverflowError):exact.enqueue(sample)
        self.assertEqual(exact.status()['usage'],before)
        reduced=Spool(self.path,max_bytes=1)
        self.assertGreater(reduced.status()['usage']['payload_bytes'],reduced.status()['limits']['payload_bytes'])
        self.assertEqual(reduced.status()['usage'],before)


class DeliveryCapacityApiTests(unittest.TestCase):
    login=fixtures.AcquisitionRegistryApiTests.login
    def setUp(self):
        fixtures.AcquisitionRegistryApiTests.setUp(self)
        self.path=Path(self.temp.name)/'capacity-spool.sqlite3'
        env=patch.dict(os.environ,{'EDGEOPS_DELIVERY_SPOOL_DB':str(self.path)});env.start();self.addCleanup(env.stop)
        self.spool=Spool(self.path)
        for sequence in range(2):
            data=envelope();data['observation']['sequence']=sequence;self.spool.enqueue(data)

    def test_supported_readers_receive_global_usage_without_mutating_queue(self):
        with self.spool.db() as db:before=[tuple(row) for row in db.execute('SELECT * FROM delivery_spool ORDER BY event_key')]
        expected=self.spool.status()['usage']
        for role in ('admin','operator','auditor'):
            self.login(role)
            for state in ('','pending','blocked'):
                response=self.http.get('/api/acquisition/delivery',params={'state':state,'limit':1})
                self.assertEqual(response.status_code,200);data=response.json()
                self.assertEqual(data['usage'],expected);self.assertEqual(set(data['usage']),{'records','payload_bytes'})
                for flag in ('hardware_connected','equipment_authorized','production_ready','model_deployed'):self.assertIs(data[flag],False)
        self.http.cookies.clear();self.assertEqual(self.http.get('/api/acquisition/delivery').status_code,401)
        with self.spool.db() as db:self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM delivery_spool ORDER BY event_key')],before)
