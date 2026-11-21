"""Read-only local service observations. No hardware or production certification."""
import hashlib
from pathlib import Path
import shutil
import sqlite3
import time
from datetime import datetime, timezone

STARTED = time.monotonic()
CORE_TABLES = ('users', 'sessions', 'audit', 'comparison_reviews', 'comparison_review_events',
               'maintenance_requests', 'maintenance_request_events', 'readiness_records',
               'readiness_events', 'readiness_release_scope', 'readiness_scope_events',
               'acquisition_bindings', 'acquisition_binding_events', 'acquisition_observations',
               'synthetic_incidents', 'synthetic_incident_events', 'incident_assignments', 'incident_followups', 'incident_investigation_keys', 'incident_observation_sources', 'incident_observation_attachments', 'incident_triage', 'incident_plan_links', 'maintenance_exercises', 'maintenance_exercise_events', 'account_controls', 'account_control_events', 'account_reauth_denials')


def database_status(path, detailed=False):
    path = Path(path)
    if not path.is_file():
        return {'status': 'unavailable'}
    db = None
    try:
        db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=1)
        deadline = time.monotonic() + 1
        db.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # Existing stores have these durable domains; no database is created by a probe.
        required = set(CORE_TABLES)
        if not required.issubset(tables):
            return {'status': 'unavailable'}
        result = {'status': 'available'}
        if detailed:
            if db.execute('PRAGMA quick_check(1)').fetchall() != [('ok',)]:
                return {'status': 'unavailable'}
            result['records'] = {table: db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]
                                 for table in CORE_TABLES if table in tables}
            result['file_bytes'] = path.stat().st_size
        return result
    except (OSError, sqlite3.Error):
        return {'status': 'unavailable'}
    finally:
        if db is not None:
            db.close()


def diagnostics(database, root):
    store = database_status(database, detailed=True)
    files = ('server.py', 'team_accounts.py', 'maintenance_exercises.py', 'incidents.py', 'acquisition_registry.py', 'delivery_service.py', 'edge_delivery.py', 'observation_queries.py', 'physical_build.py', 'physical-build-plan.json', 'request_limits.py', 'operations.py', 'recovery.py',
             'maintenance_requests.py', 'production_readiness.py', 'readiness_catalog.json')
    try:
        fingerprint = hashlib.sha256()
        for name in files:
            fingerprint.update(name.encode() + b'\0' + hashlib.sha256((root / name).read_bytes()).digest())
        source = fingerprint.hexdigest()
        free = shutil.disk_usage(Path(database).parent).free
    except OSError:
        source, free = None, None
    return {'status': 'available' if store['status'] == 'available' and source else 'degraded',
            'observed_at': datetime.now(timezone.utc).isoformat(),
            'uptime_seconds': int(time.monotonic() - STARTED), 'database': store,
            'source_fingerprint': source, 'storage_free_bytes': free,
            'mode': 'local-development', 'hardware_connected': False, 'model_deployed': False,
            'production_ready': False, 'recovery_target_verified': False,
            'backup_scope': 'operator-managed; verify and restore drill required'}
