"""Request-boundary, denial-audit and observable-service regression tests."""
from contextlib import closing
import asyncio
import importlib
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import operations
from request_limits import RequestBodyLimit


class RequestBoundaryTests(unittest.TestCase):
    def run_request(self, chunks, headers=None, limit=8):
        observed, sent = [], []
        async def application(scope, receive, send):
            observed.append((await receive())['body'])
            await send({'type': 'http.response.start', 'status': 204, 'headers': []})
            await send({'type': 'http.response.body', 'body': b''})
        messages = [{'type': 'http.request', 'body': chunk, 'more_body': i < len(chunks)-1}
                    for i, chunk in enumerate(chunks)]
        async def receive():
            return messages.pop(0) if messages else {'type': 'http.disconnect'}
        async def send(message):
            sent.append(message)
        asyncio.run(RequestBodyLimit(application, limit)(
            {'type': 'http', 'method': 'POST', 'headers': headers or []}, receive, send))
        return observed, sent

    def test_stream_without_content_length_cannot_bypass_limit(self):
        observed, sent = self.run_request([b'12345', b'6789', b'not read'])
        self.assertFalse(observed)
        self.assertEqual(sent[0]['status'], 413)
        self.assertIn((b'cache-control', b'no-store'), sent[0]['headers'])

    def test_lying_length_and_duplicate_or_invalid_length_are_rejected(self):
        self.assertEqual(self.run_request([b'123456789'], [(b'content-length', b'1')])[1][0]['status'], 413)
        for value in [b'-1', b'bad', b'9' * 100]:
            self.assertEqual(self.run_request([b'1'], [(b'content-length', value)])[1][0]['status'], 400)
        self.assertEqual(self.run_request([b'1'], [(b'content-length', b'1')] * 2)[1][0]['status'], 400)

    def test_exact_boundary_replays_complete_body_once(self):
        observed, sent = self.run_request([b'123', b'45678'])
        self.assertEqual(observed, [b'12345678'])
        self.assertEqual(sent[0]['status'], 204)


class ServiceOperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='edgeops-operations-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.database = Path(cls.temp.name) / 'dashboard.sqlite3'
        cls.email, cls.password = 'operations@example.invalid', secrets.token_urlsafe(24)
        env = patch.dict(os.environ, {'EDGEOPS_DASHBOARD_DB': str(cls.database),
                                    'EDGEOPS_ADMIN_EMAIL': cls.email, 'EDGEOPS_ADMIN_PASSWORD': cls.password})
        env.start()
        cls.addClassCleanup(env.stop)
        import server
        cls.server = importlib.reload(server)
        cls.server.init_db()

    def setUp(self):
        self.http = TestClient(self.server.app)
        self.addCleanup(self.http.close)

    def login(self):
        self.assertEqual(self.http.post('/api/auth/login', json={
            'email': self.email, 'password': self.password}).status_code, 200)

    def test_failed_login_is_retained_after_denial(self):
        self.assertEqual(self.http.post('/api/auth/login', json={
            'email': 'nonexistent@example.invalid', 'password': 'wrong'}).status_code, 401)
        with closing(sqlite3.connect(self.database)) as db:
            actor, detail = db.execute("SELECT actor,detail FROM audit WHERE action='login_failed' ORDER BY id DESC").fetchone()
        self.assertEqual(actor, 'unauthenticated')
        self.assertNotIn('wrong', detail)

    def test_liveness_readiness_and_private_diagnostics(self):
        self.assertEqual(self.http.get('/health/live').status_code, 200)
        self.assertEqual(self.http.get('/health/ready').json(), {'status': 'available', 'production_ready': False})
        self.assertEqual(self.http.get('/api/system/diagnostics').status_code, 401)
        self.login()
        data = self.http.get('/api/system/diagnostics').json()
        self.assertEqual(data['database']['status'], 'available')
        self.assertEqual(len(data['source_fingerprint']), 64)
        self.assertFalse(data['production_ready'])
        self.assertFalse(data['hardware_connected'])
        self.assertNotIn(str(self.database), str(data))
        self.assertNotIn(self.password, str(data))
        with self.server.database() as db:
            db.execute("UPDATE users SET role='operator' WHERE email=?", (self.email,))
        try:
            self.assertEqual(self.http.get('/api/system/diagnostics').status_code, 403)
        finally:
            with self.server.database() as db:
                db.execute("UPDATE users SET role='admin' WHERE email=?", (self.email,))

    def test_missing_or_corrupt_store_is_not_reported_healthy(self):
        missing = Path(self.temp.name) / 'missing.sqlite3'
        self.assertEqual(operations.database_status(missing)['status'], 'unavailable')
        self.assertFalse(missing.exists())
        corrupt = Path(self.temp.name) / 'corrupt.sqlite3'
        corrupt.write_bytes(b'not a SQLite database')
        self.assertEqual(operations.database_status(corrupt)['status'], 'unavailable')
        with patch.object(self.server, 'DB_PATH', missing):
            self.assertEqual(self.http.get('/health/ready').status_code, 503)

    def test_large_streamed_json_does_not_reach_login(self):
        response = self.http.post('/api/auth/login', content=iter([b'{"x":"', b'a' * 9000, b'"}']),
                                  headers={'content-type': 'application/json'})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
