# EDGEOPS industrial monitoring workspace

Status: authenticated local development platform. Hardware will be connected later. This is not an accepted industrial production deployment.

The dashboard provides 18 workspaces plus sign-in. Working local services include authenticated sessions, CSRF, audit, a 30-category planning catalog, a synthetic telemetry ledger, verified offline experiments/comparisons, independent report review, saved maintenance planning and the full 53-criterion readiness evidence register. Equipment cards/charts and incident examples remain synthetic; profile previews never change account permissions.

## Current documentation

- [Production design and staged implementation](../production-design/README.md)
- [Current functionality and boundaries](PRODUCT_WORKSPACE.md)
- [Fixed 30-product physical build view](PHYSICAL_BUILD_VIEW.md)
- [Synthetic acquisition bindings and observation preflight](ACQUISITION_FOUNDATION.md)
- [Durable synthetic delivery, receipts and worker](DURABLE_DELIVERY.md)
- [Persisted telemetry, source quality and age semantics](PERSISTED_TELEMETRY.md)
- [Production gap audit and next implementation sequence](SYSTEM_AUDIT.md)
- [Backup, verification and restoration runbook](RECOVERY.md)
- [Maintenance planning and authority](MAINTENANCE_PLANNING.md)
- [All 53 readiness criteria and acceptance conditions](PRODUCTION_READINESS.md)
- [Current visual system and readability](THEME.md)

The superseded accumulated setup guide is preserved in [history](history/README-before-operations-audit.md), clearly separated from current instructions. Historical test evidence remains historical; it is not a current deployment certificate.

## Local setup and access

The existing installation uses the user's Windows checkout and http://127.0.0.1:8877/app. If it is already running, refresh that page; do not start a second server or replace the existing database/password.

For a new checkout, use Python 3.12 or newer and create a local virtual environment from this dashboard folder:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

For a fresh database only, set EDGEOPS_ADMIN_EMAIL and a unique EDGEOPS_ADMIN_PASSWORD of at least 14 characters through your local environment/secure terminal prompt. Never put real passwords in tracked files. The first configured administrator is created only when there are no users. Changing bootstrap variables does not reset an existing account. Existing installations must retain their configured EDGEOPS_DASHBOARD_DB and report paths.

```powershell
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8877
```

Keep this development server on loopback. HTTPS-only cookies require HTTPS; the environment example is documentation and is not automatically loaded as a secrets file. Production identity, managed credentials, TLS deployment and network isolation remain separate work.

## Service observations

Settings > Service checks & recovery shows the current data-store check, service uptime, available storage and source fingerprint. Admin/auditor accounts can refresh and export diagnostics; operators cannot access private diagnostics. Failed checks clear previous results and disable export until recovery.

- GET /health/live: process response only, not hardware or production readiness.
- GET /health/ready: minimal database/schema availability; returns 503 if unavailable.
- GET /api/system/diagnostics: authenticated admin/auditor observations, bounded integrity check and record counts. No passwords, account names or local paths are returned.

These checks cannot establish sensor freshness, model performance, accepted recovery targets or production availability. A healthy software probe never marks a readiness criterion accepted.

## Saved synthetic incidents

Persisted Telemetry can explicitly create an incident from a saved observation whose test-binding asset matches a dashboard asset. All six readings and declared quality/time/source identity are frozen with the case; no fault is detected automatically. Incidents can also retain up to 20 additional explicitly attached observations with reasons, exact asset/site checks and frozen evidence in history/export and planning context. Severity reviews preserve the original classification while recording the current decision and reason; the queue offers current-severity filtering and critical-first order. New linked planning drafts use current severity without rewriting earlier captured context. Saved incident details include a compact case summary, six keyboard section shortcuts and searchable/filterable history while preserving unsaved notes and complete exports. The Evidence section can compare two captured observations with quality-aware arithmetic differences and a separate read-only comparison export; values and original records remain unchanged. In-app draft protection warns before incident refresh/close/switch, intentional attachment cancellation or a save that would replace other unsaved form changes; Keep editing is the default. This does not autosave drafts or protect browser reload/tab closure. Alert center supports accountable ownership and scoped assigned-to-me views for enabled local accounts. Its investigation log retains progress, analysis and evidence-reference entries without changing the incident state, with exact retry protection after lost responses. It saves explicit incident exercises with acknowledgement, resolution evidence references, reopening, revision conflict checks and full history/export. Follow-up dates support upcoming, overdue and undated filters with explicit UTC entry, change reasons and revision history. Operators see records they created or are currently assigned; administrators and auditors can read all local exercises, with auditors read-only. Open or acknowledged incidents can create linked maintenance drafts with a frozen source revision and visible change warnings; approval still requires an independent reviewer. See [incident workflow and limits](INCIDENT_WORKFLOW.md). No incidents are seeded, and these records perform no live detection, escalation, equipment action or repair verification.

## Maintenance documentation exercises

Current independently approved plans now offer saved synthetic documentation exercises with notes, evidence references, independent exercise review, history/export and plan-revision guards. Exercise review never verifies physical work or authorizes equipment. See [maintenance exercise workflow and limits](MAINTENANCE_EXERCISES.md). No exercise records are seeded.

## Local team accounts

Administrators can now manage local account creation, roles and access from Settings > Accounts for independent review. Administrators can also rotate a local password explicitly, with confirmation and session revocation. Every change requires the administrator password, a reason and a fresh revision; access changes revoke target sessions and protect the last active administrator. Existing credentials are preserved and no accounts are seeded. See [local account controls and remaining identity work](TEAM_ACCOUNTS.md).

## Hardware arrival download

Inventory > Your ordered hardware now offers **Download hardware arrival pack**. All signed-in read roles can download the fixed 30-product worksheet, conditional connection references, firmware source, V1 capture/V2 evidence tools, synthetic examples and their offline software tests. The authenticated ZIP endpoint is `/api/hardware/physical-plan/arrival-pack`; it exports only a fixed source-file list, never the dashboard database, credentials or local captures. A missing source or changed hardware matrix fails the whole download. File hashes support corruption checks, not source authentication or release acceptance.

Start with `START-HERE.md` in the ZIP. The receipt worksheet is an offline copy; editing it does not update the dashboard or establish receipt, connection, calibration or production readiness. All 30 selected products retain their identities and existing roles.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The complete local run during this audit collected 132 cases: 108 passed and 24 Python-browser cases were skipped because the Python Playwright package is not installed locally. Four separate Node/Chromium suites passed against disposable databases: the complete 18-view workspace, readiness, maintenance planning and saved comparison review. Their screenshots and contrast reports are generated under the ignored .acceptance-captures folder. The workspace suite includes persisted test bindings, preflight/retirement and diagnostics refresh/export/outage recovery and text-size checks at five widths. GitHub workflows run their own current-head checks; consult actual results rather than inferring success from committed source.

## GitHub updates

Current work is proposed in draft PR #2 from ui/production-workspace-20261119 into dashboard-live-edit. Saving a local file does not upload it. Review the diff and checks before merging. Do not blindly pull over uncommitted changes, run an auto-push watcher during an update, commit .local data, or overwrite the current accounts/reports/plans.

## Production boundary

A complete production claim requires the exact deployed scope, real measurements, implemented authoritative domain services, identity and delivery integrations, validated intelligence, recovery/load evidence and qualified acceptance. See SYSTEM_AUDIT.md for the actual remaining software and hardware work. Adding a dashboard page or marking evidence as accepted cannot substitute for these results.
