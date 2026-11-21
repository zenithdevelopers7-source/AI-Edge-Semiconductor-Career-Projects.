# Local backup and recovery runbook

Scope: the current SQLite development application and immutable synthetic experiment artifacts. This is not PostgreSQL disaster recovery, an encrypted backup service, or proof of accepted recovery time/data-loss targets. Hardware is not operated by this tool.

## What is preserved

`recovery.py` snapshots the configured dashboard database using SQLite's backup API, including committed WAL data. All tables are retained: users/password hashes/roles, comparison reviews/history, maintenance requests/history, readiness evidence/reviews/scope and audit. An optional separate synthetic telemetry database and optional content-addressed experiment directory are included only when explicitly supplied. Backups use standalone SQLite files, hashes, table counts, integrity checks and an exact file inventory.

Passwords, account metadata and evidence remain private. The backup is not encrypted or signed. Directory modes restrict access on systems supporting those modes; Windows operators must set appropriate folder ACLs and use protected/encrypted storage. Hashes detect accidental changes against a trusted manifest, not an attacker replacing both data and manifest. Protect a trusted manifest hash separately if authenticity is required.

## Backup and verify

Run from the dashboard folder, using the database/artifact locations actually configured for that installation. The following paths are defaults, not discovery of your environment. Never infer that an omitted store was backed up.

```powershell
.\.venv\Scripts\python.exe recovery.py backup --database .local/dashboard.sqlite3 --artifacts .local/experiments --output .local/backups/checkpoint-01
.\.venv\Scripts\python.exe recovery.py verify .local/backups/checkpoint-01
```

Add `--telemetry .local/synthetic-telemetry.sqlite3` if that store exists and must be preserved. If there is no experiments directory yet, omit `--artifacts`; supplying a nonexistent path fails rather than silently skipping it. Choose a new output name for each backup. Never commit backup folders or share them as public test artifacts.

Each SQLite snapshot is consistent independently. Databases and artifact copies are not one distributed transaction. Stop all application and experiment writers for a coordinated application recovery point; an online backup is a per-store snapshot. Configure scheduled backups, retention, encryption and an off-machine copy through the deployment's operational controls; these are not automatically installed by this CLI.

## Restore drill before an incident

```powershell
.\.venv\Scripts\python.exe recovery.py restore .local/backups/checkpoint-01 --output .local/restore-drills/checkpoint-01
```

The tool verifies the complete backup before publishing restored files and refuses an existing destination. It never overwrites the live database. It restores into a new directory, reconciles counts and produces `restore-report.json`. Existing browser sessions are removed from the restored copy and a recovery audit event is added. Accounts/passwords/roles, reports/plans/evidence and prior audit entries are preserved. Sign in again after a real cutover. Browser-only scratchpad and local display preferences are not server backups.

Use a separate loopback service/port and explicitly point `EDGEOPS_DASHBOARD_DB` to the drill's dashboard.sqlite3, `EDGEOPS_OFFLINE_EXPERIMENT_ROOT` to its artifacts folder, and the synthetic telemetry variable to its restored file if included. Inspect actual accounts, plan/report/evidence history and verified experiment visibility. Do not set a replacement bootstrap password for an existing restored account. Stop the drill service afterward. Measure elapsed time and record exceptions before accepting any recovery objective.

For an actual incident, stop the service, preserve the damaged state for investigation, verify and drill the chosen backup, then explicitly configure the service to the reviewed restored paths. Cutover and remote deployment are operator decisions; this tool does not change running service configuration.

## Failure behavior and limits

Missing/corrupt databases, broken foreign keys, altered artifacts, duplicate/traversing paths, linked files/directories, unlisted files and integrity/count mismatches fail closed. Incomplete work is staged separately and is not published as a successful backup/restore. Current limits are 10,000 files and 2 GiB of payloads. Only the five current JSON experiment families are supported, with SHA-256 names matching contents. Other operational files, model formats, configuration/secrets, identity-provider state and external services need their own reviewed backup procedures.

The verification suite exercises committed WAL data, preservation and session invalidation, corruption, unsafe paths, unsupported additions, existing destinations and missing sources. It does not establish field reliability, encrypted off-site storage, full disaster recovery or a production SLA.

Implementation reference: [Python sqlite3 backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup).

## Delivery spool

If present, include the configured delivery spool with `--delivery-spool .local/delivery-spool.sqlite3` during backup. This preserves pending/delivered/blocked identities, receipt records and inflight leases. On restoration, expired leases are reclaimed by the next worker attempt; unexpired leases wait. Include the dashboard database and spool together, stopping writers for a coordinated recovery point. The tool does not start a worker or requeue blocked entries.
