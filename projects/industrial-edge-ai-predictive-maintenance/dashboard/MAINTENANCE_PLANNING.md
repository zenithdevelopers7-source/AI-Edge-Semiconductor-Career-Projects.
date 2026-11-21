# Authenticated local maintenance planning

This service stores **synthetic-asset planning requests**, not operational work orders. Every response declares `scope=local-synthetic-planning`, `equipment_authorized=false`, `hardware_connected=false` and `execution_enabled=false`. Report review, model release and equipment operation remain separate domains.

## Working journey

1. An admin or operator creates a draft for one of the 12 existing synthetic asset IDs. Title, observation and proposed inspection are required; evidence references are plain text, not uploaded or verified files.
2. The creator can revise the draft and submit an exact record revision with a reason.
3. A **different admin account** can approve or reject the submitted revision, with a required reason. An administrator has no self-review bypass. These are local account checks; they do not establish enterprise identity or prove that different accounts represent different people.
4. A creator can withdraw a submitted request to draft. Submitted content is otherwise frozen.
5. Editing an approved or rejected request returns it to draft, clears its current review metadata and retains the historical decision. A rejected request must be revised before resubmission.

The UI exposes creator actions and reviewer actions from service-provided capabilities, but the service independently checks every mutation. The profile preview selector grants no permission. The browser-session scratchpad and the seven-stage execution walkthrough remain separate from saved records. A scratchpad can be copied into a new form only by an explicit user action.

## Access boundaries

| Account role | Read scope | Write scope |
| --- | --- | --- |
| Operator | Own requests and their history | Create, revise, submit and withdraw own requests |
| Admin | All local planning requests | Create/revise own requests; independently review another creator's submitted revision |
| Auditor | All local planning requests and history | None |
| Other/unrecognized | Denied | Denied |

All writes require an active opaque session and its matching CSRF token. The transaction rechecks the current user, role, disabled flag and session after obtaining the SQLite write lock. A revoked session or role cannot rely on an earlier authorization result. Existing same-origin/body-size/security-header controls also apply.

## Contracts and consistency

| Endpoint | Behavior |
| --- | --- |
| `GET /api/maintenance-requests` | Scoped queue, status/title/asset search, counts and pagination; max 50 records/page |
| `GET /api/maintenance-requests/{id}` | Authorized current record and revision/decision history |
| `GET /api/maintenance-requests/{id}/revisions/{revision}` | Authorized read-only historical content, with no mutation capabilities |
| `POST /api/maintenance-requests` | Retry-safe creation using a creator-scoped 32-character `request_key` |
| `PUT /api/maintenance-requests/{id}` | Creator-only revision; requires strict integer `expected_revision` |
| `POST /api/maintenance-requests/{id}/actions` | Submit/withdraw/approve/reject, strict expected revision and required note |

`BEGIN IMMEDIATE` serializes revision checks, state/content updates, immutable-by-application history snapshots and matching audit events. A stale revision returns 409 without partially committing. An identical creation retry returns the same record; reusing its save key for different initial content returns 409. Input contracts forbid extra fields and unsupported asset IDs, priorities and actions.

History events preserve the prior approved/submitted content snapshot. `reviewed_revision` names the submitted record revision used for the review, while `revision` also advances for state transitions. Editing invalidates current review metadata; it never rewrites earlier history. These local SQLite records are not an externally protected, tamper-proof audit service.

The interface rejects unsupported response scope, clears unavailable queues, disables unverified create/filter actions, preserves typed conflict notes, and ignores delayed detail responses after a different form has opened. No optimistic approval is shown before the service confirms a decision.

## Storage and verification

Startup adds `maintenance_requests` and `maintenance_request_events` tables and an index to the existing local database; users, sessions, reports and audit records are preserved. The installation process creates a consistent SQLite backup before enabling the extension. No additional package dependency or automatic account creation is needed.

Eight isolated API tests cover authorization/CSRF/read scope, retry-safe creation, independent review, approval invalidation, rejection/resubmission, concurrent edit serialization, revocation during authorization, validation and pagination/search. A separate Chromium suite uses disposable users/databases to exercise persistence, asset context, literal evidence text, independent review, conflicts, rejection/history, administrator self-review denial, auditor read-only access, service recovery, delayed detail responses and five viewport widths. Test users and test requests are never installed into the user's live local database.

Production work remains: enterprise identity and independently governed reviewer grants, real assets and evidence validation, field work-order execution/verification, protected audit infrastructure, deployment/recovery acceptance and physical commissioning. With a single local admin account, its own requests intentionally cannot be reviewed until a different authorized reviewer is provisioned through an appropriate account-management process.
