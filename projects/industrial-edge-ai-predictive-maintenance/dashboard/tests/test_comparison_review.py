"""Saved comparison integrity, review authorization, concurrency and history."""
import importlib
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_registry import save_comparison, verify_comparison
from run_offline_experiment import synthetic_fixture


class ComparisonReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.password = secrets.token_urlsafe(24)
        self.env = patch.dict(os.environ, {
            "EDGEOPS_DASHBOARD_DB": str(self.root / "auth.sqlite3"),
            "EDGEOPS_ADMIN_EMAIL": "reviewer@example.invalid",
            "EDGEOPS_ADMIN_PASSWORD": self.password,
            "EDGEOPS_OFFLINE_EXPERIMENT_ROOT": str(self.root / "experiments")})
        self.env.start()
        import server
        self.server = importlib.reload(server)
        self.server.init_db()
        self.http = TestClient(self.server.app)
        self.saved = save_comparison(synthetic_fixture(), self.root / "experiments")
        self.id = self.saved["comparison_id"]
        self.url = "/api/model-comparisons/" + self.id + "/review"

    def tearDown(self):
        self.http.close()
        self.env.stop()
        self.temp.cleanup()

    def login(self):
        response = self.http.post("/api/auth/login", json={
            "email": "reviewer@example.invalid", "password": self.password})
        self.assertEqual(response.status_code, 200)
        return {"x-edgeops-csrf": self.http.cookies.get("edgeops_csrf")}

    def body(self, revision=0, status="approved", note="Synthetic report reviewed; no deployment approval."):
        return {"expected_revision": revision, "status": status, "note": note}

    def test_01_content_addressed_save_and_tamper_detection(self):
        repeated = save_comparison(synthetic_fixture(), self.root / "experiments")
        self.assertEqual(self.id, repeated["comparison_id"])
        report = verify_comparison(self.root / "experiments", self.id)
        self.assertEqual(report["result"]["split"]["test_count"], 10)
        path = self.root / "experiments" / "comparison-datasets" / (report["dataset_sha256"] + ".json")
        path.write_text("{}", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_comparison(self.root / "experiments", self.id)
        with self.assertRaises(ValueError):
            save_comparison(synthetic_fixture(), self.root / "experiments")

    def test_02_review_lifecycle_revision_conflict_and_history(self):
        headers = self.login()
        data = self.http.get("/api/model-comparisons").json()
        self.assertEqual(data["comparisons"][0]["review"]["status"], "pending")
        self.assertNotIn("rows", str(data))
        for revision, status in enumerate(("approved", "rejected", "pending")):
            response = self.http.post(self.url, headers=headers,
                                      json=self.body(revision, status))
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["review"]["revision"], revision + 1)
            self.assertFalse(response.json()["model_deployed"])
        self.assertEqual(self.http.post(self.url, headers=headers,
                                       json=self.body(0)).status_code, 409)
        comparison = self.http.get("/api/model-comparisons").json()["comparisons"][0]
        self.assertEqual([x["status"] for x in comparison["review_history"]],
                         ["pending", "rejected", "approved"])
        self.assertTrue(all(x["note"] for x in comparison["review_history"]))
        with self.server.database() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM audit WHERE action='offline_comparison_review'").fetchone()[0], 3)
        self.assertFalse(self.http.get("/api/system/health").json()["actuators_enabled"])

    def test_03_auth_csrf_and_role_required(self):
        self.assertEqual(self.http.get("/api/model-comparisons").status_code, 401)
        self.assertEqual(self.http.post(self.url, json=self.body()).status_code, 401)
        headers = self.login()
        self.assertEqual(self.http.post(self.url, json=self.body()).status_code, 403)
        for role in ("operator", "auditor"):
            with self.server.database() as db:
                db.execute("UPDATE users SET role=?", (role,))
            self.assertFalse(self.http.get("/api/model-comparisons").json()["can_review"])
            self.assertEqual(self.http.post(self.url, headers=headers, json=self.body()).status_code, 403)

    def test_04_tampered_report_hidden_and_cannot_be_approved(self):
        headers = self.login()
        path = self.root / "experiments" / "comparisons" / (self.id + ".json")
        path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.http.get("/api/model-comparisons").json()["comparisons"], [])
        self.assertEqual(self.http.post(self.url, headers=headers, json=self.body()).status_code, 409)
        with self.server.database() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM comparison_reviews").fetchone()[0], 0)

    def test_05_invalid_review_and_id_rejected(self):
        headers = self.login()
        for body in (self.body(note="   "), self.body(status="deployed"),
                     self.body(-1), {"status": "approved", "note": "Missing revision"}):
            self.assertEqual(self.http.post(self.url, headers=headers, json=body).status_code, 422)
        self.assertEqual(self.http.post("/api/model-comparisons/invalid/review", headers=headers,
                                       json=self.body()).status_code, 422)
        self.assertEqual(self.http.post("/api/model-comparisons/" + "0" * 64 + "/review",
                                       headers=headers, json=self.body()).status_code, 409)

    def test_06_invalid_dataset_writes_nothing(self):
        rows = synthetic_fixture()
        del rows[0]["label"]
        destination = self.root / "invalid"
        with self.assertRaises((ValueError, KeyError)):
            save_comparison(rows, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
