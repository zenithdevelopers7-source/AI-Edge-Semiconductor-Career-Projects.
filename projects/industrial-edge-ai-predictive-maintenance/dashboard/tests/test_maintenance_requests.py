"""Isolated local planning authorization, revisions, audit and concurrency."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class MaintenancePlanningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="edgeops-planning-")
        self.password = secrets.token_urlsafe(24)
        self.env = patch.dict(os.environ, {"EDGEOPS_DASHBOARD_DB": str(Path(self.temp.name)/"test.db"),
            "EDGEOPS_ADMIN_EMAIL": "reviewer@example.invalid", "EDGEOPS_ADMIN_PASSWORD": self.password})
        self.env.start()
        import server
        self.server = importlib.reload(server)
        self.server.init_db()
        encoded = self.server.password_hash(self.password)
        with self.server.database() as db:
            for email, role in (("creator@example.invalid", "operator"), ("other@example.invalid", "operator"), ("audit@example.invalid", "auditor")):
                db.execute("INSERT INTO users(email,password_hash,role) VALUES(?,?,?)", (email, encoded, role))
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.env.stop()
        self.temp.cleanup()

    def client(self, email):
        client = TestClient(self.server.app)
        self.clients.append(client)
        response = client.post("/api/auth/login", json={"email": email, "password": self.password})
        self.assertEqual(response.status_code, 200)
        return client, {"x-edgeops-csrf": client.cookies.get("edgeops_csrf")}

    def body(self, **changes):
        return {"request_key": secrets.token_hex(16), "asset_id": "MTR-001", "title": "Review motor sensor context",
                "observation": "Synthetic acceleration needs quality review.", "proposal": "Inspect the signal provenance and calibration references.",
                "evidence_refs": "Synthetic fixture, not a physical observation.", "priority": "medium", **changes}

    def create(self, client, headers, **changes):
        response = client.post("/api/maintenance-requests", headers=headers, json=self.body(**changes))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["equipment_authorized"])
        return response.json()["request"]

    def act(self, client, headers, row, action, expected=200):
        response = client.post("/api/maintenance-requests/"+row["id"]+"/actions", headers=headers,
            json={"expected_revision": row["revision"], "action": action, "note": "Reviewed synthetic planning evidence; no field execution."})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json().get("request")

    def edit_body(self, row, **changes):
        return {key: value for key, value in {**self.body(), "expected_revision": row["revision"], **changes}.items() if key != "request_key"}

    def test_01_auth_csrf_roles_and_private_operator_scope(self):
        guest = TestClient(self.server.app)
        self.clients.append(guest)
        self.assertEqual(guest.get("/api/maintenance-requests").status_code, 401)
        self.assertEqual(guest.post("/api/maintenance-requests", json=self.body()).status_code, 401)
        creator, csrf = self.client("creator@example.invalid")
        self.assertEqual(creator.post("/api/maintenance-requests", json=self.body()).status_code, 403)
        row = self.create(creator, csrf)
        other, other_csrf = self.client("other@example.invalid")
        self.assertEqual(other.get("/api/maintenance-requests").json()["total"], 0)
        self.assertEqual(other.get("/api/maintenance-requests/"+row["id"]).status_code, 404)
        self.assertEqual(other.put("/api/maintenance-requests/"+row["id"], headers=other_csrf, json=self.edit_body(row)).status_code, 404)
        auditor, audit_csrf = self.client("audit@example.invalid")
        self.assertEqual(auditor.get("/api/maintenance-requests").json()["total"], 1)
        self.assertFalse(auditor.get("/api/maintenance-requests").json()["can_create"])
        self.assertEqual(auditor.post("/api/maintenance-requests", headers=audit_csrf, json=self.body()).status_code, 403)
        admin, admin_csrf = self.client("reviewer@example.invalid")
        self.assertEqual(admin.put("/api/maintenance-requests/"+row["id"], headers=admin_csrf, json=self.edit_body(row)).status_code, 403)

    def test_02_retry_safe_creation_and_content_conflict(self):
        creator, csrf = self.client("creator@example.invalid")
        payload = self.body()
        first = creator.post("/api/maintenance-requests", headers=csrf, json=payload).json()
        second = creator.post("/api/maintenance-requests", headers=csrf, json=payload).json()
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["request"]["id"], second["request"]["id"])
        self.assertEqual(creator.post("/api/maintenance-requests", headers=csrf, json={**payload, "title": "Different planning content"}).status_code, 409)
        with self.server.database() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM maintenance_request_events").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE action='maintenance_planning_created'").fetchone()[0], 1)

    def test_03_independent_review_revision_binding_and_approval_invalidation(self):
        creator, csrf = self.client("creator@example.invalid")
        admin, admin_csrf = self.client("reviewer@example.invalid")
        row = self.create(creator, csrf)
        submitted = self.act(creator, csrf, row, "submit")
        self.assertFalse(submitted["actions"]["edit"])
        self.assertEqual(creator.put("/api/maintenance-requests/"+row["id"], headers=csrf, json=self.edit_body(submitted)).status_code, 409)
        approved = self.act(admin, admin_csrf, submitted, "approve")
        self.assertEqual(approved["reviewed_revision"], submitted["revision"])
        self.act(admin, admin_csrf, submitted, "reject", 409)
        edited = creator.put("/api/maintenance-requests/"+row["id"], headers=csrf, json=self.edit_body(approved, title="Revised sensor inspection scope"))
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()["request"]["status"], "draft")
        self.assertIsNone(edited.json()["request"]["reviewed_revision"])
        self.assertEqual([e["action"] for e in edited.json()["history"]], ["edited", "approved", "submitted", "created"])
        historical = creator.get("/api/maintenance-requests/"+row["id"]+"/revisions/2").json()
        self.assertTrue(historical["read_only"])
        self.assertEqual(historical["snapshot"]["title"], "Review motor sensor context")
        self.assertEqual(historical["snapshot"]["status"], "submitted")
        self.assertNotIn("creator_id", historical["snapshot"])
        with self.server.database() as db:
            snapshot = json.loads(db.execute("SELECT snapshot_json FROM maintenance_request_events WHERE revision=3").fetchone()[0])
            self.assertEqual(snapshot["title"], "Review motor sensor context")
            self.assertEqual(snapshot["reviewed_revision"], 2)
        self.assertFalse(edited.json()["execution_enabled"])

    def test_04_admin_has_no_self_review_bypass(self):
        admin, csrf = self.client("reviewer@example.invalid")
        row = self.act(admin, csrf, self.create(admin, csrf), "submit")
        self.assertFalse(row["actions"]["review"])
        self.act(admin, csrf, row, "approve", 403)
        self.act(admin, csrf, row, "reject", 403)
        withdrawn = self.act(admin, csrf, row, "withdraw")
        self.assertEqual(withdrawn["status"], "draft")

    def test_05_rejection_requires_revision_before_resubmission(self):
        creator, csrf = self.client("creator@example.invalid")
        admin, admin_csrf = self.client("reviewer@example.invalid")
        row = self.act(creator, csrf, self.create(creator, csrf), "submit")
        rejected = self.act(admin, admin_csrf, row, "reject")
        self.act(creator, csrf, rejected, "submit", 409)
        revised = creator.put("/api/maintenance-requests/"+row["id"], headers=csrf, json=self.edit_body(rejected)).json()["request"]
        self.assertEqual(self.act(creator, csrf, revised, "submit")["status"], "submitted")

    def test_06_concurrent_edits_commit_exactly_one_revision(self):
        creator, csrf = self.client("creator@example.invalid")
        row = self.create(creator, csrf)
        def save(title):
            client = TestClient(self.server.app)
            client.cookies.update(creator.cookies)
            try:
                return client.put("/api/maintenance-requests/"+row["id"], headers=csrf, json=self.edit_body(row, title=title)).status_code
            finally:
                client.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ("Concurrent proposal one", "Concurrent proposal two")))
        self.assertEqual(sorted(results), [200, 409])
        data = creator.get("/api/maintenance-requests/"+row["id"]).json()
        self.assertEqual(data["request"]["revision"], 2)
        self.assertEqual(len(data["history"]), 2)

    def test_07_revocation_rechecked_inside_write_transaction(self):
        creator, csrf = self.client("creator@example.invalid")
        admin, admin_csrf = self.client("reviewer@example.invalid")
        row = self.act(creator, csrf, self.create(creator, csrf), "submit")
        with self.server.database() as db:
            stale = dict(db.execute("SELECT u.id,u.email,u.role,s.csrf_hash,s.expires_at FROM users u JOIN sessions s ON u.id=s.user_id WHERE email='reviewer@example.invalid'").fetchone())
            db.execute("UPDATE users SET role='auditor' WHERE email='reviewer@example.invalid'")
        with patch.object(self.server, "auth_context", return_value=stale):
            self.act(admin, admin_csrf, row, "approve", 403)
        with self.server.database() as db:
            db.execute("UPDATE users SET disabled=1 WHERE email='reviewer@example.invalid'")
        with patch.object(self.server, "auth_context", return_value=stale):
            self.act(admin, admin_csrf, row, "approve", 401)

    def test_08_payload_validation_and_pagination_search(self):
        creator, csrf = self.client("creator@example.invalid")
        for changes in ({"asset_id": "REAL-MOTOR"}, {"title": "        "}, {"priority": "urgent"}, {"equipment_authorized": True}):
            self.assertEqual(creator.post("/api/maintenance-requests", headers=csrf, json=self.body(**changes)).status_code, 422)
        for index in range(5):
            row = self.create(creator, csrf, title="Review 100% evidence" if index==0 else "Inspect synthetic motor "+str(index))
        response = creator.get("/api/maintenance-requests?limit=2&offset=2").json()
        self.assertEqual(response["total"], 5)
        self.assertEqual(len(response["requests"]), 2)
        self.assertEqual(creator.get("/api/maintenance-requests", params={"q":"%"}).json()["total"], 1)
        self.assertEqual(creator.get("/api/maintenance-requests?status=active").status_code, 422)
        for revision in (True, 0, "1"):
            self.assertEqual(creator.put("/api/maintenance-requests/"+row["id"], headers=csrf, json=self.edit_body(row, expected_revision=revision)).status_code, 422)


if __name__ == "__main__":
    unittest.main()
