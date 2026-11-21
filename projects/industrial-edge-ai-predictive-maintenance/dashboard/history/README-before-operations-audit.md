# Superseded dashboard guide

Historical snapshot before the operations audit of 19 November 2026. Commands, counts, screenshots and status claims below may be outdated. Use the active dashboard README and linked runbooks.

# EDGEOPS — Industrial Intelligence Platform

**Status: authenticated local development application; production acceptance remains open.**

The current workspace has 18 connected views plus sign-in: overview, assets, telemetry, incidents, maintenance, AI insights, device operations, models, knowledge, simulation, hardware, architecture, reports, security, governance, production readiness, people/profiles and settings.

See [product workspace coverage and verification](PRODUCT_WORKSPACE.md) for every implemented interaction and service boundary. Start system design with [the consolidated production design](../production-design/README.md). Historical visual prototypes have moved to [the superseded prototype archive](../archive/ui-prototypes/README.md).

The working local service provides opaque authenticated sessions, CSRF-protected actions, SQLite audit history, a read-only 30-category planning catalog, integrity-verified synthetic experiments, scoped offline report review, and persistent synthetic maintenance planning with independent-account review. Hardware purchases/instances and commissioning remain unverified. Equipment charts and incidents are synthetic. Professional profiles, maintenance walkthroughs, device readiness and simulation are clearly labeled previews. No live model deployment, enterprise identity, operational work-order approval, or equipment command is provided.

The inspection scratchpad is browser-session only. Saved maintenance planning requests use the authenticated service and retain revisions/decisions; see [planning contracts and access rules](MAINTENANCE_PLANNING.md). Profile previews do not alter the signed-in account or server permissions. A report approval is never a work-order approval or model release.

## Run from Cursor / VS Code on Windows

Open the existing Git checkout in Cursor or VS Code, then run **PowerShell** in the integrated terminal:

~~~powershell
cd "C:\Users\Gaming PC i9 3080\edgeops-workspace\projects\industrial-edge-ai-predictive-maintenance\dashboard"
git pull --ff-only origin main
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
~~~

Create a strong local development password (do **not** save it in source code, screenshots or Git). The following prompt reads the password securely without displaying it in your terminal:

~~~powershell
$env:EDGEOPS_ADMIN_EMAIL = "admin@example.invalid"
$secure = Read-Host "New EDGEOPS local admin password (14+ chars)" -AsSecureString
$handle = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:EDGEOPS_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($handle)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($handle)
  Remove-Variable secure
}
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8765
~~~

**Open:** http://127.0.0.1:8765/signin

The first run creates the local admin and development database in the ignored `.local/` directory. Restarting the same database will not change the original admin password merely by changing the environment variables. Setting `EDGEOPS_HTTPS_ONLY=1` requires HTTPS (typically at an authenticated reverse proxy) or cookies will not work over HTTP. This setup is strictly localhost-only; do not bind 0.0.0.0 or expose the development server to the internet.

**Verification from another terminal:**

~~~powershell
cd "C:\Users\Gaming PC i9 3080\edgeops-workspace\projects\industrial-edge-ai-predictive-maintenance\dashboard"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_server.py" -v
~~~

This suite has **12 authored API tests**: redirects, login rejection, session, catalog, no static server-source access, CSRF, logout, audit, safe state and synthetic-only acknowledgment.

**Static checks:** The Phase 1 static structure test has been updated for the authenticated server asset routes. Both source structure and API tests are configured in GitHub Actions but remain unverified until their actual run results are inspected.

## GitHub + Cursor/VS Code automatic synchronization

**Git principle:** Editing and saving a file locally does *not* automatically update GitHub. Saving, staging, committing and pushing are separate operations. Automatically pushing every keystroke to `main` would risk publishing untested code and secrets.

Recommended human-review workflow:

~~~powershell
git status
git diff -- projects/industrial-edge-ai-predictive-maintenance/dashboard
git add projects/industrial-edge-ai-predictive-maintenance/dashboard
git commit -m "feat(edgeops): improve dashboard"
git push origin main
~~~

These commands are written for running from the **repository root**. For simple day-to-day work from this dashboard folder use `git add index.html styles.css app.js signin.html signin.css signin.js server.py` with only the files you actually reviewed; do not stage local `.env` or `.local/` data.

**Optional continuous auto-commit and push:** Only if you explicitly enable it, `sync-dashboard.ps1` can watch for edits every 20 seconds, commit an allowlist of dashboard source files and push to a **separate `dashboard-live-edit` branch** (never directly to `main`). Before starting:

~~~powershell
git fetch origin
git switch -c dashboard-live-edit
git push -u origin dashboard-live-edit
.\sync-dashboard.ps1 -Watch -IntervalSeconds 20
~~~

This is a convenience workflow, not CI. Stop with Ctrl+C. It refuses unrelated staged files and aborts when push fails. **Review the diff and run tests before merging that branch into main.** Do not save tokens or secrets in source files, since even a temporary commit can expose them remotely. The monitor uses the existing Git credentials configured in Cursor or VS Code; do not paste GitHub personal access tokens into scripts.

## What remains before a truthful production claim

| Area | Current implementation | Required before production |
|---|---|---|
| Sign-in | Local bootstrap admin and session cookies | Enterprise identity (OIDC/SSO), MFA, provisioning, recovery and account policies |
| Authorization | Fixed local roles for read-only/audit endpoints | Tenant/site/asset authorization and policy integration |
| UI | Responsive code committed | Actual multi-browser visual QA, accessibility audit and UX acceptance |
| Data | Synthetic fixtures and isolated SQLite auth/audit | PostgreSQL/TimescaleDB, migrations, retention, recovery, integrations |
| MQTT | EA-31 localhost mTLS lab separate from dashboard | Durable retries/queue, proven delivery semantics, hardening, certificate lifecycle |
| Analytics | Synthetic static charts | Live read-only API with provenance, pagination and error states |
| Predictive AI | Illustrative cards only | Trained/evaluated models, drift monitoring, calibrated explanations and human review |
| Device operations | Proposed 30-slot catalog | Bill of materials approval, physical provisioning, certificates and calibration |
| Security | Local CSRF, session and headers starter | Independent pen test, OIDC, distributed rate limiting, secure deployment, secrets manager, SIEM |
| Safety | No actuator UI, G4b BLOCKING | Independent electrical safety/guard/E-stop approval before physical testing |
| Reliability | Some EA-30/31 lab evidence | EA-32 spool/retry/dead-letter design and failure-injection proof |
| Governance | Architecture and test documents | Change control, runbooks, disaster recovery tests, threat model sign-off |

**Do not deploy this local starter as an internet-facing production identity service or connect real industrial equipment.**

## Source

- `signin.html`, `signin.css`, `signin.js`: login experience.
- `index.html`, `styles.css`, `app.js`: existing multi-page dashboard.
- `dashboard-auth.js`: authenticated inventory loading and logout.
- `server.py`: local API, session storage, auth and audit.
- `tests/test_server.py`: authored security/API tests; local execution pending.
- `sync-dashboard.ps1`: opt-in Git sync for dedicated development branch.


## Approved visual redesign — sign-in and executive command center

**Design status:** Source implemented on `dashboard-live-edit`, awaiting browser screenshot/visual QA and an updated local test run. Not yet merged to `main` and not a production deployment.

The approved dark command-center direction has been rebuilt with brighter text, electric cyan outlines, industrial midnight-blue surfaces and amber status/actions. Industrial machinery imagery is shipped as two original local SVG assets, `industrial-motor.svg` and `industrial-plant.svg`, both served through an explicit static allowlist. The source illustrations are stylized vector art, not photorealistic images or actual photographs of purchased hardware.

### Sign-in layout

- Full-width industrial illustration with overlaid synthetic sensor readouts and a distinct access card.
- Local account login, show/hide password, optional remembered **email only** (not password), and explicit feedback for unconfigured SSO, recovery and public demo access.
- Mobile responsive layout with keyboard focus treatments.
- Corporate safety notice, demo provenance and readable accessible contrast.

### Executive dashboard

- Compact eleven-section navigation: Overview, Assets, Telemetry, AI Copilot, Inventory, Alerts, Maintenance, Security, Governance, Reports and Settings.
- Five executive KPI fixtures (health, 30 planned hardware slots, alerts, model readiness and illustrative uptime).
- Machine + sensor hero display, selectable sensor signal chart, alerts, activity, demonstration work queue and review-only quick actions.
- Synthetic fleet distribution; equipment criticality; maintenance queue; pictorial hardware preview; governance/safety panel.
- Functional read-only inventory API, alert browsing/ephemeral acknowledge, snapshot JSON export, session sign-out, section navigation and client-only asset/alert search.
- No deceptive "30 connected devices", "deployed model" or production-risk statistics. The 30 component positions are **planning slots**, and only 14 component names are confirmed from the user's earlier requested inventory.

### Preview on your Windows machine

Because you have an opt-in auto-sync watcher on the development branch, press **Ctrl+C in the sync terminal before pulling** to avoid local/remote divergence during updates.

```powershell
cd "C:\Users\Gaming PC i9 3080\edgeops-workspace\projects\industrial-edge-ai-predictive-maintenance\dashboard"
git status
git pull --ff-only origin dashboard-live-edit
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_structure.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_server.py" -v
```

Keep the preexisting Uvicorn development server running on localhost port 8877. Open:

- http://127.0.0.1:8877/signin
- http://127.0.0.1:8877/app (after authenticated sign-in)

With `--reload`, the server may restart due to Python source changes. **Use Ctrl+F5 to hard-refresh** CSS, JS and SVG assets as needed. In a separate terminal restart the opt-in watcher with `.\sync-dashboard.ps1 -Watch -IntervalSeconds 20` once the branch has been pulled and tested.

### Verification scope

The dashboard is not pixel-identical to generated mockup images: the approved composition, contrast, features and colors have been translated into maintainable HTML/CSS/JS, with local vector machinery artwork rather than the mockup's photorealistic pixels. Source changes are committed to the GitHub branch, but no actual browser screenshot or new test output has been verified yet. Do not count new checks as passed until the test log and UI are inspected.


## Approved reference photographs (November 18)

The dashboard and login now reference two JPG images extracted/cropped from the user-approved EDGEOPS mockup:
- `edgeops-motor-photo.jpg`: photographed industrial motor with existing cyan sensor overlays.
- `edgeops-factory-backdrop.jpg`: wider factory environment used behind the sign-in showcase.

**The binary JPGs must be copied into this directory locally**, then added and pushed from the user's checkout. They are not bundled in this branch by GitHub's text-file connector. Until installed, an error handler falls back to the original vector SVG illustrations. The backend serves both JPGs only through its static allowlist. This is intentional and avoids a broken image or a silent claim that the image was uploaded.

Copy both files into `dashboard/` and in PowerShell:
```powershell
git add -- edgeops-motor-photo.jpg edgeops-factory-backdrop.jpg
git commit -m "assets(edgeops): add approved industrial photographic artwork"
git push origin dashboard-live-edit
```

Run `python -m unittest discover -s tests -p "test_server.py" -v`, reload the page and check the browser's Network panel for 200 responses on both image URLs. Do not publish the entire reference screenshot as a user background with the simulated login form duplicated on top.


## User experience refinement — readability & operational navigation

This revision keeps the existing locally authenticated architecture demo and prioritizes actual UX improvements over more imagery:
- Increased text contrast, minimum body legibility and card section clarity.
- Added interactive asset search and filter (all, critical, watch, nominal) with a visible result count.
- Added demo alert filtering (all, open, acknowledged, critical).
- Added `Focus` mode to expand the executive workspace for desktop review.
- Mobile navigation now has a tap-to-close backdrop and Escape-key dismissal.
- Improved form labels, field styling, chart captions and table scanning at smaller widths.
- Kept synthetic metrics and local read-only safety disclosures visible.

The changes are source commits on `dashboard-live-edit`; they are not automatically merged to `main`. Review after pulling the branch. Run:
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_structure.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_server.py -v
```
The refined UI should also be checked manually at desktop and mobile widths before merging.


## Enterprise Architecture Explorer — next portfolio milestone

Added an interactive **Architecture** navigation page that explains the system from end to end, with eight selectable stages:

1. Guarded sensors and bench rig (planned)
2. ESP32 telemetry acquisition (planned)
3. MQTT mutual TLS transport (software-lab evidence)
4. FastAPI edge validation gateway (software-lab evidence)
5. SQLite local event persistence and replay (software-lab evidence)
6. AI and agent orchestration (not deployed)
7. Authenticated enterprise access API (local demo)
8. Read-only executive operations console (local demo)

Each stage can be inspected for: architectural purpose, technologies, security/safety boundary, failure handling, evidence/readiness and the key design decision. View controls also emphasize security boundaries or failure-handling considerations. Supporting panels distinguish verification history from deployment readiness.

**Scope guardrails:** There is no live topology, no real hardware telemetry, no production SSO, no deployed AI model, and no actuator commands. MQTT/mTLS and replay claims refer to controlled local test fixtures, not operational certification.

### Verify on Windows

Pull `dashboard-live-edit` while the optional Git auto-sync watcher is paused. With the local authenticated Uvicorn server active on port 8877, open `http://127.0.0.1:8877/app`, choose **Architecture**, select each of the eight components, and verify the inspector updates. Try **Security boundaries** and **Failure handling**. Confirm keyboard focus, long-text overflow and mobile layout.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_structure.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_server.py -v
```

This UI and its source checks establish a reviewable architecture portfolio narrative, not a deployable enterprise solution or independently audited safety system.


## Interface completion hardening — reliability and navigation

Prior to further architectural phases, the signed-in dashboard now includes:
- Visible local API health status and session identity/expiry in the Security & Audit tab
- Authenticated, read-only local audit-event viewer with refresh and clear empty/error/access-denied states
- Hardware inventory loading, retry, fail-closed empty state and metrics calculated from authenticated API results
- 12-second bounded API requests and explicit session-expiry navigation to sign-in
- Shareable navigation fragments (e.g. `/app#architecture`, `/app#security`) with Back/Forward support
- Additional structural regression coverage for these interface behaviors

**UI QA checklist:** sign in, verify Overview, all 12 sidebar sections, search, asset filters, alert filters and acknowledgment behavior, architecture tabs, report export, session/audit display, inventory refresh, sign out, and 390px/768px/1440px layouts. The local API health chip is not live plant health.

**Readiness boundary:** this is UI implementation and static/API regression hardening, not production readiness. Real infrastructure, SaaS tenancy, live telemetry, model inference, industrial safety and deployment evidence remain separate later phases.


## Synthetic telemetry persistence and offline evaluation foundation (November 2026)

The development server now exposes a deliberately **synthetic-only** telemetry event ledger. It does not connect industrial sensors or deploy a predictive model.

- `POST /api/synthetic-telemetry` accepts validated demo events only from the authenticated local admin, with the same CSRF protection as existing mutations. Each event **must** state `"provenance": "synthetic-demo"`; other provenance values are rejected.
- `GET /api/synthetic-telemetry?asset_id=MTR-001&limit=100` returns persisted demo events for authenticated users, including provenance and explicit `model_deployed: false`.
- `telemetry_store.py` persists events by unique `event_id` with stable-content SHA-256 fingerprints. Identical replays are idempotent; conflicting replays return HTTP 409.
- Data is stored **separately** from account/session/audit data in the ignored `.local/synthetic-telemetry.sqlite3` file. Override with `EDGEOPS_SYNTHETIC_TELEMETRY_DB` only when explicitly using an isolated test database. The existing `.local/dashboard.sqlite3` is not migrated or rewritten.
- `ml_evaluation.py` provides deterministic precision/recall/F1/confusion-matrix calculations for supplied **labeled** scores, and a chronological holdout split helper. This is an **evaluation foundation**, not a trained model or any accuracy result. Sensor fixtures alone cannot establish equipment-failure ground truth.
- CI tests cover API authentication/CSRF, provenance rejection, range validation, idempotency, conflict responses, persisted reads, and offline evaluation. All CI tests use isolated temporary databases.

Example event body (send only with an authenticated local session and a matching `x-edgeops-csrf` header):

```json
{
  "event_id": "demo-mtr001-0001",
  "asset_id": "MTR-001",
  "captured_at": "2026-11-18T12:00:00+00:00",
  "vibration_mm_s": 2.6,
  "temperature_c": 41.2,
  "current_a": 1.7,
  "provenance": "synthetic-demo"
}
```

**Next validation gates:** time-series replay/retention and ingestion throughput; labeled failure dataset provenance, split leakage controls, calibrated model evaluation, explainability, model registry, drift detection, and human review. None of these is claimed complete by the synthetic ledger.


## Offline time-series feature engineering and baseline (November 2026)

The next testable milestone adds **pure-Python offline analysis** without modifying the dashboard's live view, stored sessions, or protected telemetry APIs:

- `time_series_features.py`: deterministic, per-asset trailing windows. Calculates vibration, temperature and current latest/mean/population standard deviation/change. Sorting is by timezone-aware event timestamp; future rows are excluded, and cross-asset mixing, missing/nonfinite data, duplicate event IDs/timestamps and non-synthetic provenance are rejected.
- `offline_baseline.py`: reproducible **demonstration anomaly baseline** from explicitly labeled feature rows. Sorts chronologically into train, validation and holdout partitions; standardization parameters are fit on training only, alert threshold is chosen on validation only, and test metrics are computed only once on the chronological holdout. The anomaly score is **not a failure probability**.
- `ml_evaluation.py`: reusable confusion-matrix, precision, recall, F1 and accuracy calculations for labeled evaluation data.

The tests use deterministic **synthetic demonstration labels**, not measured industrial failures. No real-world predictive accuracy, calibrated failure probabilities, remaining useful life, model deployment or edge inference is established. The baseline stays offline and is never connected to hardware controls.

Check locally with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_server.py -v
```

**Further work:** quality-controlled labeled failure histories, leakage-aware per-asset temporal splits with time-gap embargo, train-only feature scaling, baseline comparisons with scikit-learn, registered experiment artifacts, real validation metrics and industrial review gates.


## Offline ML experiment registry (November 2026)

`experiment_registry.py` adds content-addressed, **local-only** experiment tracking for the offline, synthetic-label baseline. Experiments include an immutable snapshot of explicitly labeled features, model parameters (JSON, **not pickle**), chronological split configuration, holdout metrics and SHA-256 artifact fingerprints. Identical inputs and configuration produce the same run ID; changes in configuration create a separate run.

The registry writes into the exact folder supplied by the caller. Use a **new ignored directory** such as `.local/experiments`, not the authentication SQLite database. No API endpoint exposes experiment files, no cloud uploads occur and no model is deployed.

Example from the dashboard folder, after preparing a list of labeled feature rows:

```python
from experiment_registry import register_experiment, verify_experiment, compare_experiments

registered = register_experiment(labeled_synthetic_feature_rows, ".local/experiments")
verified = verify_experiment(".local/experiments", registered["run_id"])
comparison = compare_experiments(".local/experiments", [registered["run_id"]])
```

`labeled_synthetic_feature_rows` is deliberately not supplied as real failure evidence. The caller must provide valid explicitly labeled synthetic demonstration rows. The stored JSON model specification is **not** an approved deployable model, calibration artifact, or proof of predictive reliability.

Verify using `python -m unittest discover -s tests -p test_experiment_registry.py -v`. Integrity tests detect overwritten files and inconsistent artifact hashes. A dedicated GitHub Actions workflow runs the same checks. Keep production or personal data out of these demo artifacts.

**Future gates:** curated real labeled histories, dataset licensing/provenance, leakage/embargo review, model comparison with approved baselines, experiment approvals, security review, calibration and monitored deployment.

### Run two reproducible synthetic experiments from PowerShell

From the EDGEOPS dashboard folder, without starting a server:

```powershell
.\.venv\Scripts\python.exe run_offline_experiment.py --output ".local/experiments"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_experiment_registry.py -v
```

The command prints two content-addressed run IDs and a comparison of **synthetic holdout** metrics. It writes immutable JSON dataset snapshots, model parameter specifications and experiment reports into `.local/experiments/{datasets,models,runs}`. Re-running with identical inputs does not create a new run. The demo does not train or deploy a supervised industrial failure model; the labels and telemetry are generated exclusively for repeatable software testing.


## Fair-split scikit-learn baseline comparison and report viewer (November 2026)

**Offline model comparison:** optional `requirements-ml.txt` provides NumPy and scikit-learn. `sklearn_comparison.py` evaluates a transparent standardized-deviation baseline alongside an independently fitted `LogisticRegression` pipeline. Both use the **same chronological train, validation and test partitions**. Scaling is fit only on training; each threshold is chosen on validation; the common test set is not used for fitting or threshold selection. Scores and metrics are for invented **synthetic labels** and must never be described as equipment-failure accuracy, calibration or a production model.

Run locally from `dashboard/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_sklearn_comparison.py -v
.\.venv\Scripts\python.exe run_sklearn_comparison.py
```

**Dashboard report viewer:** the existing `Reports` page now includes a read-only table populated by `GET /api/offline-experiments`. This endpoint requires a logged-in user and verifies SHA-256 dataset/model/run JSON artifacts from `.local/experiments` before returning **summary metrics only**. Corrupt or altered records are never displayed; the frontend shows an explicit empty/error state and a Retry control. It never returns raw dataset rows or enables model inference or equipment commands.

To see the locally generated experiments, keep your authenticated local FastAPI server running on port 8877, open `http://127.0.0.1:8877/app#reports`, and select **Refresh experiments**. These previously saved registry experiments can have **different holdout sizes** and are not a fair model comparison. Use the separate scikit-learn CLI for equal-holdout offline comparisons. UI snapshot data remains illustrative.

**Production blockers remain:** real labeled failure events, quality and leakage review, measured operational performance, model approval and deployment, physical hardware safeguards and independent security testing.

## Saved model comparisons and offline report review

The comparison CLI can now save the equal-holdout scikit-learn comparison for the authenticated Reports page:

```powershell
.\.venv\Scripts\python.exe run_sklearn_comparison.py --output ".local/experiments"
```

The original command without `--output` still prints results without saving artifacts. Saved comparisons live in `.local/experiments/comparisons` and reference a fingerprinted synthetic dataset in `comparison-datasets`. Records include split settings, thresholds, software versions, both models' metrics and common holdout IDs. Repeating identical inputs under the same software versions produces the same comparison ID. Metrics remain synthetic demonstrations on a tiny sample, not field performance. These reports do not contain deployable model binaries.

Restart the existing local FastAPI server after installing the update, then sign in and open `http://127.0.0.1:8877/app#reports`. Select **Refresh comparisons** under **Saved Model Comparisons & Review**. Existing offline experiments retain their separate table.

- Every authenticated user can view verified comparison summaries, review status and the latest 20 review events. Dataset rows are never returned by this API.
- Only an authenticated **admin** with a matching CSRF token can approve, reject or return an offline report to pending. A nonblank review note is required.
- Status begins as pending. Decisions record the reviewer, UTC time, full note and revision in SQLite. All review events are retained; the UI shows the latest 20. A corresponding audit event is committed in the same transaction.
- The submitted revision must match the current revision; an outdated view gets HTTP 409 and must refresh. Missing or altered comparison/dataset files cannot be reviewed and are excluded from the list.
- Approval always means **offline report review only**. No model deployment, inference or equipment controls are enabled. Byte integrity does not establish scientific validity or authenticity against an attacker who can replace the entire local registry.

`GET /api/model-comparisons` reads summaries; `POST /api/model-comparisons/{comparison_id}/review` accepts `{status, note, expected_revision}`. The existing `EDGEOPS_OFFLINE_EXPERIMENT_ROOT` override applies to both registries. Startup adds review tables to the existing dashboard database without deleting accounts, sessions or prior audit records. Back up the database before applying updates to any valuable local installation.

Verification:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_comparison_review.py -v
```

The scikit-learn GitHub workflow now runs the saved-report and review checks as well as the original comparison tests. Real datasets, scientific review, hardware integration, deployment and industrial validation remain outstanding.

## Operations workspace UI refresh

The authenticated dashboard now uses a consistent slate/teal visual system across all 12 sections, grouped navigation, and a matching sign-in page. Press **Ctrl+K** (or **Command+K**) to search sections, demo assets and alerts. Select an asset name to inspect its details. The asset registry supports combined filters, sorting and clear-filters. Telemetry includes an accessible sample table and synthetic CSV export. Settings provides a browser-local table spacing preference and keyboard shortcut help.

Equipment views remain synthetic fixtures. The overview uses the same signal source and units as the telemetry explorer; it does not show a fabricated uptime SLA or failure probability. Authenticated local inventory, audit events and verified saved experiments retain their existing API behavior. A concise source indicator distinguishes these views, and an API check time is never represented as a sensor timestamp.

`workspace.css` defines the shared workspace styling; `workspace.js` contains the new interactions. Both are served through the existing static-asset allowlist. All fonts and illustrations load locally. See [UI/UX review and production gates](UI_UX_REVIEW.md) for project context, validation limits and the remaining implementation work.

The browser workflow runs `tests/browser_workspace.cjs` using Playwright for Node in addition to the existing Python and saved-comparison checks. It verifies all 12 sections at five viewport widths and the new keyboard, dialog, export and preference workflows against a disposable local account/database.
