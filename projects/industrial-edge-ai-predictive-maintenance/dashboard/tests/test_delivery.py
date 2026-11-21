"""Durability, response loss, lease fencing, identity conflicts and real HTTP delivery."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import httpx
from pydantic import ValidationError
from edge_delivery import Spool,identity
from delivery_service import DeliveryInput
from delivery_worker import run_once
import test_acquisition_registry as fixtures
from test_acquisition_registry import binding,observation


def envelope():
    sample=observation();sample['boot_id']='synthetic-boot';sample['quality']['session_quality']='verified'
    return DeliveryInput.model_validate({'binding_revision':1,'observation':sample}).model_dump(mode='json')


class SpoolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='edgeops-spool-');self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'spool.sqlite3';self.spool=Spool(self.path)

    def due(self):
        with self.spool.db() as db:db.execute('UPDATE delivery_spool SET next_at=0,lease_until=0')

    def receipt(self,claim):return {'tier':'central-committed','event_key':claim['event_key'],'content_hash':claim['content_hash'],'receipt_id':'test-only-receipt'}

    def test_restart_replay_and_capacity_do_not_lose_committed_event(self):
        first=self.spool.enqueue(envelope());restarted=Spool(self.path)
        self.assertFalse(restarted.enqueue(envelope())['created'])
        self.assertEqual(restarted.status()['counts']['pending'],1)
        small=Spool(self.path,max_rows=1)
        sample=envelope();sample['observation']['sequence']=1
        with self.assertRaises(OverflowError):small.enqueue(sample)
        self.assertEqual(self.spool.status()['counts']['pending'],1)
        self.assertEqual(first['tier'],'edge-committed')
        with self.assertRaises(OverflowError):Spool(Path(self.temp.name)/'tiny.sqlite3',max_bytes=10).enqueue(envelope())

    def test_abrupt_process_exit_and_backup_restore_preserve_pending_queue(self):
        script="import os,sys,json;from edge_delivery import Spool;s=Spool(sys.argv[1]);s.enqueue(json.loads(sys.argv[2]));s.claim();os._exit(0)"
        subprocess.run([sys.executable,'-c',script,str(self.path),json.dumps(envelope())],check=True,cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(Spool(self.path).status()['counts']['inflight'],1)
        self.due();self.assertIsNotNone(Spool(self.path).claim())
        from recovery import create_backup,restore_backup
        import sqlite3
        from contextlib import closing
        auth=Path(self.temp.name)/'auth.sqlite3'
        with closing(sqlite3.connect(auth)) as db:
            db.executescript('CREATE TABLE users(id INTEGER);CREATE TABLE sessions(token_hash TEXT);CREATE TABLE audit(time_utc TEXT,actor TEXT,action TEXT,detail TEXT);')
        backup=Path(self.temp.name)/'backup';restored=Path(self.temp.name)/'restored'
        create_backup(auth,backup,delivery_spool=self.path);restore_backup(backup,restored)
        self.assertEqual(Spool(restored/'delivery-spool.sqlite3').status()['counts']['inflight'],1)

    def test_semantic_hash_excludes_arrival_but_detects_content_change(self):
        self.spool.enqueue(envelope())
        sample=envelope();sample['observation']['timestamp']['gateway_received_utc']='2026-11-20T10:00:00Z'
        self.assertFalse(self.spool.enqueue(sample)['created'])
        sample['observation']['measurements']['acceleration_x_mps2']=2
        with self.assertRaises(ValueError):self.spool.enqueue(sample)
        sample=envelope();sample['observation']['source_type']='measured'
        with self.assertRaises(ValidationError):self.spool.enqueue(sample)

    def test_expired_lease_is_reclaimed_and_old_worker_cannot_finish(self):
        self.spool.enqueue(envelope());old=self.spool.claim();self.due();new=self.spool.claim()
        self.assertNotEqual(old['token'],new['token'])
        self.assertFalse(self.spool.finish(old,receipt=self.receipt(old)))
        self.assertTrue(self.spool.finish(new,receipt=self.receipt(new)))
        self.assertEqual(self.spool.status()['counts']['delivered'],1)

    def test_retry_backoff_permanent_denial_and_invalid_receipt(self):
        self.spool.enqueue(envelope())
        self.spool.attempt(lambda data:(_ for _ in ()).throw(TimeoutError('test secret must not be saved')))
        self.assertIsNone(self.spool.claim())
        self.assertNotIn('secret',str(self.spool.status()))
        self.due();self.spool.attempt(lambda data:(409,{}))
        self.assertEqual(self.spool.status()['counts']['blocked'],1)
        other=envelope();other['observation']['sequence']=2;self.spool.enqueue(other)
        self.spool.attempt(lambda data:(200,[]))
        self.assertEqual(self.spool.status()['counts']['blocked'],2)
        sample=envelope();sample['observation']['sequence']=3;self.spool.enqueue(sample)
        for _ in range(8):
            self.due();self.spool.attempt(lambda data:(503,{}))
        self.assertEqual(self.spool.status()['counts']['blocked'],3)

    def test_concurrent_claim_and_disk_error_do_not_acknowledge_uncommitted_data(self):
        self.spool.enqueue(envelope())
        with ThreadPoolExecutor(max_workers=2) as pool:claims=list(pool.map(lambda _:self.spool.claim(),range(2)))
        self.assertEqual(sum(c is not None for c in claims),1)
        # A read-only connection supplies a real SQLite write failure without filling the user's disk.
        import sqlite3
        from contextlib import contextmanager
        from unittest.mock import patch
        @contextmanager
        def readonly():
            db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
            try:yield db
            finally:db.close()
        sample=envelope();sample['observation']['sequence']=9
        with patch.object(self.spool,'db',readonly),self.assertRaises(sqlite3.OperationalError):self.spool.enqueue(sample)
        self.assertEqual(sum(self.spool.status()['counts'].values()),1)


class DeliveryApiTests(unittest.TestCase):
    login=fixtures.AcquisitionRegistryApiTests.login
    post=fixtures.AcquisitionRegistryApiTests.post
    # Reuse isolated accounts/bootstrap, not the parent's test cases.
    def setUp(self):
        fixtures.AcquisitionRegistryApiTests.setUp(self);self.assertEqual(self.post('/api/acquisition-bindings',binding()).status_code,201)

    def test_delivery_commit_response_loss_and_conflict(self):
        data=envelope();spool=Spool(Path(self.temp.name)/'delivery-spool.sqlite3');spool.enqueue(data)
        def lost_response(payload):
            response=self.post('/api/acquisition/ingest',payload);self.assertEqual(response.status_code,201)
            raise TimeoutError('response lost after actual commit')
        spool.attempt(lost_response)
        self.assertEqual(spool.status()['counts']['pending'],1)
        with spool.db() as db:db.execute('UPDATE delivery_spool SET next_at=0')
        spool.attempt(lambda payload:(lambda r:(r.status_code,r.json()))(self.post('/api/acquisition/ingest',payload)))
        self.assertEqual(spool.status()['counts']['delivered'],1)
        data['observation']['measurements']['acceleration_x_mps2']=3
        self.assertEqual(self.post('/api/acquisition/ingest',data).status_code,409)
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM acquisition_observations').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE action='synthetic_ingest_conflict'").fetchone()[0],1)

    def test_queue_retirement_roles_and_ambiguous_session_denial(self):
        data={'binding_revision':1,'observation':observation()}
        self.assertEqual(self.post('/api/acquisition/queue',data).status_code,422)
        self.assertEqual(self.post('/api/acquisition/queue',envelope()).status_code,201)
        self.assertEqual(self.http.get('/api/acquisition/delivery').json()['central_records'],0)
        self.assertEqual(self.post('/api/acquisition-bindings/test-device/retire',{'expected_revision':1}).status_code,200)
        self.assertEqual(self.post('/api/acquisition/deliver-once',{}).status_code,200)
        self.assertEqual(self.http.get('/api/acquisition/delivery').json()['counts']['blocked'],1)
        self.login('auditor');self.assertEqual(self.post('/api/acquisition/deliver-once',{}).status_code,403)
        self.assertEqual(self.post('/api/acquisition/ingest',envelope()).status_code,403)

    def test_real_loopback_worker_transmits_and_commits(self):
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
        env={**os.environ,'EDGEOPS_ADMIN_EMAIL':'','EDGEOPS_ADMIN_PASSWORD':''}
        service=subprocess.Popen([sys.executable,'-m','uvicorn','server:app','--host','127.0.0.1','--port',str(port)],cwd=Path(__file__).resolve().parents[1],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    if httpx.get(f'http://127.0.0.1:{port}/health/ready',trust_env=False).status_code==200:break
                except httpx.HTTPError:pass
                time.sleep(.05)
            path=Path(self.temp.name)/'remote-edge.sqlite3';Spool(path).enqueue(envelope())
            self.assertTrue(run_once(path,f'http://127.0.0.1:{port}','admin@example.invalid',self.password)['attempted'])
            self.assertEqual(Spool(path).status()['counts']['delivered'],1)
            self.assertEqual(self.http.get('/api/acquisition/delivery').json()['central_records'],1)
        finally:service.terminate();service.wait(timeout=10)
