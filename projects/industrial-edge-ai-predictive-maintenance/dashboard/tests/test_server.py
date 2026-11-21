"""Local dashboard authentication and hardware catalog API tests.

Run from dashboard dir: python -m unittest discover -s tests -p test_server.py -v
"""
import importlib
import os
import secrets
import sqlite3
from unittest.mock import patch
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class DashboardApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="edgeops-dashboard-")
        cls.db = str(Path(cls.temp.name) / "auth.sqlite3")
        cls.email = "local-tester@example.invalid"
        cls.password = secrets.token_urlsafe(24)
        os.environ["EDGEOPS_DASHBOARD_DB"] = cls.db
        os.environ["EDGEOPS_SYNTHETIC_TELEMETRY_DB"] = str(Path(cls.temp.name) / "synthetic-telemetry.sqlite3")
        os.environ["EDGEOPS_ADMIN_EMAIL"] = cls.email
        os.environ["EDGEOPS_ADMIN_PASSWORD"] = cls.password
        import server
        # Other test modules may already have imported the telemetry ledger.
        # Bind it to this suite's temporary database before any fixture writes.
        importlib.reload(server.telemetry_store)
        cls.server = importlib.reload(server)
        cls.server.init_db()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        for key in ("EDGEOPS_DASHBOARD_DB", "EDGEOPS_SYNTHETIC_TELEMETRY_DB", "EDGEOPS_ADMIN_EMAIL", "EDGEOPS_ADMIN_PASSWORD"):
            os.environ.pop(key, None)

    def setUp(self):
        self.http = TestClient(self.server.app)

    def tearDown(self):
        self.http.close()

    def sign_in(self):
        response = self.http.post("/api/auth/login",
                                  json={"email": self.email, "password": self.password})
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_01_unauthenticated_app_redirect(self):
        res = self.http.get("/app", follow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res.headers["location"], "/signin")

    def test_02_unauthenticated_inventory_denied(self):
        self.assertEqual(self.http.get("/api/hardware").status_code, 401)

    def test_03_bad_password_denied(self):
        self.assertEqual(self.http.post("/api/auth/login",
                                       json={"email": self.email, "password": "incorrect"}).status_code, 401)

    def test_04_authenticated_session(self):
        self.sign_in()
        self.assertEqual(self.http.get("/api/me").json()["role"], "admin")

    def test_05_thirty_hardware_slots_with_unconfirmed_names(self):
        self.sign_in()
        data = self.http.get("/api/hardware").json()
        self.assertEqual(len(data["devices"]), 30)
        self.assertEqual(data["confirmed_hardware_count"], 0)
        self.assertEqual(data["named_category_count"], 30)
        self.assertEqual([d["id"] for d in data["devices"]], [f"BOM-{i:02d}" for i in range(1,31)])
        self.assertTrue(all(d["lifecycle"] == "ordered-user-reported" and not d["purchase_verified"] for d in data["devices"]))
        self.assertEqual(sum(1 for d in data["devices"] if d["connected"]), 0)

    def test_06_static_file_allowlist_blocks_secrets(self):
        self.assertEqual(self.http.get("/static/server.py").status_code, 404)
        self.assertEqual(self.http.get("/static/.env").status_code, 404)
        self.assertEqual(self.http.get("/static/styles.css").status_code, 200)
        self.assertEqual(self.http.get("/static/industrial-motor.svg").status_code, 200)
        self.assertEqual(self.http.get("/static/industrial-plant.svg").status_code, 200)
        self.assertEqual(self.http.get("/static/architecture.js").status_code, 200)

    def test_07_logout_requires_csrf(self):
        self.sign_in()
        self.assertEqual(self.http.post("/api/auth/logout").status_code, 403)

    def test_08_logout_revokes_session(self):
        self.sign_in()
        csrf = self.http.cookies.get("edgeops_csrf")
        self.assertTrue(csrf)
        self.assertEqual(self.http.post("/api/auth/logout",
                                        headers={"x-edgeops-csrf": csrf}).status_code, 200)
        self.assertEqual(self.http.get("/api/me").status_code, 401)

    def test_09_authenticated_audit(self):
        self.sign_in()
        res = self.http.get("/api/audit")
        self.assertEqual(res.status_code, 200)
        self.assertIn("entries", res.json())

    def test_10_no_motor_controls_advertised(self):
        self.sign_in()
        health = self.http.get("/api/system/health").json()
        self.assertFalse(health["actuators_enabled"])
        self.assertFalse(health["hardware_connected"])
        self.assertEqual(health["physical_safety_gate"], "blocking")

    def test_11_security_headers(self):
        response = self.http.get("/signin")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    def test_12_alert_ack_is_demo_only(self):
        self.sign_in()
        csrf = self.http.cookies.get("edgeops_csrf")
        result = self.http.post("/api/alerts/acknowledge",
                                json={"alert_id": "AL-2401"},
                                headers={"x-edgeops-csrf": csrf})
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["persistent_alarm_state"])


    def test_13_synthetic_telemetry_endpoint_requires_authentication(self):
        self.assertEqual(self.http.get("/api/synthetic-telemetry").status_code, 401)
        self.assertEqual(self.http.post("/api/synthetic-telemetry", json=self.synthetic_event("evt-unauth-1")).status_code, 401)

    def test_14_synthetic_telemetry_requires_csrf_and_explicit_provenance(self):
        self.sign_in()
        event = self.synthetic_event("evt-csrf-1")
        self.assertEqual(self.http.post("/api/synthetic-telemetry", json=event).status_code, 403)
        csrf = self.http.cookies["edgeops_csrf"]
        event["provenance"] = "real-hardware"
        self.assertEqual(self.http.post("/api/synthetic-telemetry", json=event,
                                       headers={"x-edgeops-csrf": csrf}).status_code, 422)

    @staticmethod
    def synthetic_event(event_id):
        return {
            "event_id": event_id, "asset_id": "MTR-001",
            "captured_at": "2026-01-01T01:02:03+00:00",
            "vibration_mm_s": 2.6, "temperature_c": 41.2, "current_a": 1.7,
            "provenance": "synthetic-demo",
        }

    def test_15_synthetic_telemetry_durable_insert_and_idempotent_replay(self):
        self.sign_in()
        csrf = self.http.cookies["edgeops_csrf"]
        event = self.synthetic_event("evt-durable-1")
        response = self.http.post("/api/synthetic-telemetry", json=event,
                                  headers={"x-edgeops-csrf": csrf})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertTrue(response.json()["inserted"])
        self.assertFalse(response.json()["model_deployed"])
        again = self.http.post("/api/synthetic-telemetry", json=event,
                               headers={"x-edgeops-csrf": csrf})
        self.assertEqual(again.status_code, 200, again.text)
        self.assertFalse(again.json()["inserted"])
        result = self.http.get("/api/synthetic-telemetry?asset_id=MTR-001")
        self.assertEqual(result.status_code, 200)
        matches = [x for x in result.json()["events"] if x["event_id"] == "evt-durable-1"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["provenance"], "synthetic-demo")

    def test_16_synthetic_telemetry_rejects_conflicts_and_invalid_values(self):
        self.sign_in()
        csrf = self.http.cookies["edgeops_csrf"]
        headers = {"x-edgeops-csrf": csrf}
        event = self.synthetic_event("evt-conflict-1")
        self.assertEqual(self.http.post("/api/synthetic-telemetry", json=event,
                                       headers=headers).status_code, 201)
        conflict = {**event, "temperature_c": 99.0}
        self.assertEqual(self.http.post("/api/synthetic-telemetry", json=conflict,
                                       headers=headers).status_code, 409)
        for edited in ({**event, "event_id": "evt-bad-nan", "vibration_mm_s": -1},
                       {**event, "event_id": "evt-bad-tz", "captured_at": "2026-01-01T01:02:03"},
                       {**event, "event_id": "evt-bad-range", "temperature_c": 250}):
            with self.subTest(edited=edited["event_id"]):
                self.assertEqual(self.http.post("/api/synthetic-telemetry", json=edited,
                                               headers=headers).status_code, 422)


    def test_17_offline_threshold_evaluation_no_training_claim(self):
        from ml_evaluation import evaluate_scores
        result = evaluate_scores([1, 0, 1, 0], [0.9, 0.3, 0.4, 0.6], threshold=0.5)
        self.assertEqual((result.tp, result.tn, result.fp, result.fn), (1, 1, 1, 1))
        self.assertEqual(result.precision, 0.5)
        self.assertEqual(result.recall, 0.5)
        self.assertEqual(result.f1, 0.5)
        with self.assertRaises(ValueError):
            evaluate_scores([1], [float("nan")], threshold=0.5)

    def test_18_chronological_holdout_prevents_random_shuffling(self):
        from ml_evaluation import chronological_holdout
        values = [(t, t % 2, float(t)/10) for t in (5, 1, 4, 2, 3, 6)]
        train, test = chronological_holdout(values, holdout_fraction=0.33)
        self.assertEqual([row[0] for row in train], [1, 2, 3, 4])
        self.assertEqual([row[0] for row in test], [5, 6])
        with self.assertRaises(ValueError):
            chronological_holdout(values, holdout_fraction=1)


    def test_19_synthetic_sqlite_connections_are_explicitly_closed(self):
        """Context-manager exit must close handles, not only commit transactions."""
        import telemetry_store

        opened = []
        original_connect = sqlite3.connect

        class ObservedConnection(sqlite3.Connection):
            def close(self):
                super().close()

        def tracked_connect(*args, **kwargs):
            connection = original_connect(*args, factory=ObservedConnection, **kwargs)
            opened.append(connection)
            return connection

        with patch.object(telemetry_store.sqlite3, "connect", side_effect=tracked_connect):
            telemetry_store.init_store()
            telemetry_store.read_events(limit=1)
        self.assertGreaterEqual(len(opened), 2)
        for connection in opened:
            with self.subTest(connection=id(connection)):
                with self.assertRaises(sqlite3.ProgrammingError):
                    connection.execute("SELECT 1")


    def test_20_trailing_features_never_use_future_or_other_assets(self):
        from time_series_features import trailing_features
        from datetime import datetime, timedelta, timezone

        def make_event(eid, asset, minute, value):
            return {
                "event_id":eid, "asset_id":asset,
                "captured_at":(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=minute)).isoformat(),
                "vibration_mm_s":value,
                "temperature_c":10+value,"current_a":value/2,
                "provenance":"synthetic-demo",
            }
        events=[
            make_event("a3","A",3,9),
            make_event("b2","B",2,80),
            make_event("a1","A",1,1),
            make_event("a2","A",2,3),
            make_event("b1","B",1,40),
        ]
        features=trailing_features(events,window=2)
        by_id={row["event_id"]:row for row in features}
        self.assertEqual(set(by_id),{"a2","a3","b2"})
        self.assertEqual(by_id["a2"]["features"]["vibration_mm_s_mean"],2.0)
        self.assertEqual(by_id["a3"]["features"]["vibration_mm_s_mean"],6.0)
        self.assertEqual(by_id["b2"]["features"]["vibration_mm_s_mean"],60.0)
        self.assertEqual(by_id["a2"]["features"]["vibration_mm_s_delta"],2.0)
        self.assertEqual(trailing_features(list(reversed(events)),window=2),features)
        # New readings cannot retroactively alter previously computed features.
        earlier=trailing_features(events[:],window=2)
        extended=trailing_features(events+[make_event("a4","A",4,1000)],window=2)
        self.assertEqual(extended[:len(earlier)],earlier)

    def test_21_feature_engineering_rejects_missing_invalid_and_duplicate_readings(self):
        from time_series_features import trailing_features
        first = self.synthetic_event("f-first")
        second = {**first, "event_id":"f-second", "captured_at":"2026-01-01T01:03:03+00:00"}
        for invalid in (
            {**first, "provenance":"real-hardware"},
            {**first, "temperature_c":None},
            {**first, "vibration_mm_s":float("nan")},
            {**first, "captured_at":"2026-01-01T01:02:03"},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    trailing_features([invalid,second],window=2)
        with self.assertRaises(ValueError):
            trailing_features([first,first],window=2)
        with self.assertRaises(ValueError):
            trailing_features([first,{**first,"event_id":"duplicate-time"}],window=2)

    def test_22_offline_baseline_has_disjoint_chronological_splits(self):
        from offline_baseline import evaluate_offline_baseline
        from datetime import datetime, timedelta, timezone
        from time_series_features import trailing_features
        events=[]
        for n in range(22):
            events.append({
                "event_id":f"baseline-{n:02d}",
                "asset_id":"MTR-001",
                "captured_at":(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=n)).isoformat(),
                "vibration_mm_s":2+0.1*n+(3 if n>16 else 0),
                "temperature_c":30+0.15*n,
                "current_a":1+0.02*n,
                "provenance":"synthetic-demo",
            })
        features=trailing_features(events,window=3)
        for i,row in enumerate(features):
            row["label"]=int(i%5==0)
        result=evaluate_offline_baseline(features)
        self.assertEqual(result["train_count"]+result["validation_count"]+result["test_count"],len(features))
        self.assertEqual(result["evaluation_scope"],"synthetic-labeled-offline-only")
        self.assertEqual(result["deployment_status"],"not-deployed")
        self.assertEqual(result["failure_prediction_accuracy"],"not-established")
        self.assertEqual(result["holdout_event_ids"],[r["event_id"] for r in features[-result["test_count"]:] ])
        self.assertEqual(result["model"].feature_names[0],"vibration_mm_s_mean")
        self.assertIn("precision",result["test_metrics"])
        self.assertEqual(result["test_metrics"]["sample_count"],result["test_count"])
        # Determinism and input-order independence.
        rerun=evaluate_offline_baseline(list(reversed(features)))
        self.assertEqual(result["test_metrics"],rerun["test_metrics"])
        self.assertEqual(result["model"],rerun["model"])

    def test_23_baseline_rejects_unlabeled_and_non_synthetic_data(self):
        from offline_baseline import evaluate_offline_baseline
        from time_series_features import trailing_features
        from datetime import datetime, timedelta, timezone
        events=[{
            "event_id":f"n-{i}","asset_id":"MTR-001",
            "captured_at":(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=i)).isoformat(),
            "vibration_mm_s":1+i,"temperature_c":20+i,"current_a":0.5+i/10,
            "provenance":"synthetic-demo",
        } for i in range(13)]
        rows=trailing_features(events,window=3)
        with self.assertRaisesRegex(ValueError,"label"):
            evaluate_offline_baseline(rows)
        for row in rows:
            row["label"]=0
        rows[0]["provenance"]="hardware-live"
        with self.assertRaisesRegex(ValueError,"non-synthetic"):
            evaluate_offline_baseline(rows)



    def test_24_offline_experiment_api_requires_authentication(self):
        self.assertEqual(self.http.get("/api/offline-experiments").status_code, 401)

    def test_25_offline_experiment_api_returns_only_verified_synthetic_summaries(self):
        from experiment_registry import register_experiment
        from run_offline_experiment import synthetic_fixture
        with tempfile.TemporaryDirectory(prefix="edgeops-api-experiments-") as root:
            with patch.dict(os.environ, {"EDGEOPS_OFFLINE_EXPERIMENT_ROOT": root}):
                self.sign_in()
                empty = self.http.get("/api/offline-experiments").json()
                self.assertEqual(empty["experiments"], [])
                created = register_experiment(synthetic_fixture(), root)
                result = self.http.get("/api/offline-experiments").json()
                self.assertEqual(result["mode"], "synthetic-offline-only")
                self.assertFalse(result["model_deployed"])
                self.assertFalse(result["hardware_connected"])
                self.assertEqual(len(result["experiments"]), 1)
                row = result["experiments"][0]
                self.assertEqual(row["run_id"], created["run_id"])
                self.assertEqual(row["deployment_status"], "not-deployed")
                self.assertNotIn("rows", row)
                self.assertNotIn("centers", row)
                # Tampering makes the run unreadable instead of displaying stale metrics.
                report_file = Path(root) / "runs" / (created["run_id"] + ".json")
                report_file.write_text('{"f1":1.0}', encoding="utf-8")
                self.assertEqual(self.http.get("/api/offline-experiments").json()["experiments"], [])



if __name__ == "__main__":
    unittest.main(verbosity=2)
