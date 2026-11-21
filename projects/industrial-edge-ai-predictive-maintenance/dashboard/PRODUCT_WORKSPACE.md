# EDGEOPS product workspace — 19 November 2026

This implementation provides 18 connected workspace views plus sign-in, with a light cobalt/teal visual system, deep navy navigation with mint active states, readable dark text, responsive layouts, searchable and pinned destinations, keyboard support, and six professional profile previews. See [the current theme and readability checks](THEME.md). It implements the presentation and interaction layer of the consolidated design. It does not establish production readiness.

## Capability coverage

| Design workspace | Current interface and interactions | Service boundary |
| --- | --- | --- |
| Access | Sign-in, authenticated session, sign-out, denied/error handling | Working local account service; enterprise identity/recovery not connected |
| Fleet | Consistent fixture counts, attention queue, asset spotlight | Synthetic equipment |
| Assets | Search, status filter, sort, details, sensor-design context and catalog/device investigation links | Synthetic registry; commissioning/calibration persistence pending |
| Telemetry | Six persisted synthetic channels, commit-order chart, quality/age, bounded history and JSON export; original four-signal fixtures/table/CSV retained | Local synthetic records; no measured stream, calibrated clock or equipment-health claim |
| Device operations | Persistent synthetic bindings, strict observation preflight, retirement, saved synthetic queue/receipts and local relay, commissioning checklist and three receipt boundaries | Synthetic local persistence only; no physical enrollment, production credentials or broker integration |
| Incidents | Explicit saved-observation cases and additional captured evidence with exact asset/site checks and frozen provenance, saved synthetic lifecycle/investigation log, six-section workbench with searchable history and read-only captured-observation comparison and in-app draft-discard protection, and original/current severity review with scoped queue triage, scoped account assignment/handoff, declared UTC follow-up dates, overdue/upcoming filters, history/export and linked planning context | Real correlation, suppression, notifications, escalation and operational decisions pending |
| Maintenance | Authenticated saved planning requests, creator revisions/submission/withdrawal, independent admin review, decision history; separate seven-step execution preview and session scratchpad | Synthetic local planning only; no operational work order or field-execution authorization |
| AI assistant | Illustrative insights, evidence requirements, knowledge navigation | Retrieval and generation unavailable |
| Knowledge | Searchable design catalog, source context and revision/approval state | Catalog references are not approved SOPs or indexed documents |
| Models | Lifecycle, lineage, blocked release checklist, verified comparison link | Offline report review works; deployment and rollback unavailable |
| Hardware | Fixed 30-product physical build view, ordered-user-reported status, sensor map, preparation stages, exact-part checks, search/filters/details and exports | Same selected products; order is user-reported, receipt/instances/ratings/connection/commissioning remain unverified |
| Simulation | Three deterministic scenarios, next sample/reset, explicit missing values | Browser fixture only; no firmware/broker/model execution |
| Security/audit | Authenticated local audit records and session boundary | Enterprise grant/session administration pending |
| Governance | Readiness and physical/security/model acceptance context | No release authorization inferred |
| Reports | Verified experiment integrity, real scoped approval/rejection/history | Report review only; no equipment or model deployment authority |
| Production readiness | All 18 requirements, 15 demonstrations, 20 measurable targets, 30 hardware categories, scope/acceptance references, evidence reviews/history and full export | Tracking only; no automatic physical or production acceptance |
| Settings/people | Local density preference, shortcuts, six profile journeys, actual account identity | Profile preview never changes authenticated role or server permissions |

Profiles: operations, technician, approver, ML engineer, administrator and auditor. They expose responsibility-specific journeys and limitations. These previews do not replace server authorization or implement the full future role catalog. Browser session drafts are stored separately from authenticated report decisions and can be cleared. They must not contain confidential information.

## Document reconciliation

- `production-design/` is the current system design. EA milestone documents and evidence retain their historical scope.
- Removed the outdated 14-named/16-placeholder inventory definition from the running API and active dashboard guidance. `BOM-01..30` now matches the design categories. These identifiers replace the old grouped `HW-*` slots; they are not a one-to-one historical alias or a physical inventory migration.
- Removed seven obsolete HTML prototypes from the active `assets/` folder and retained their contents under `archive/ui-prototypes/`, explicitly marked superseded. This removes competing runnable UI references without deleting historical evidence. Repository Git history also retains the earlier paths.
- The source review manifest remains a dated record of its original input snapshot. It is not a current-tree integrity manifest; moved prototype paths and changed source hashes do not imply tampering with that historical snapshot.
- Physical wiring and lab evidence have not been deleted merely because a target architecture differs. Exact-part review and explicitly scoped tests still govern those records.

## Verification

On 19 November 2026, the local Python suite completed with 54 passed and 24 browser cases skipped because Python Playwright is unavailable in this environment. Two separate Chromium suites passed: saved comparison review (real isolated service, approval/rejection, persistence, escaping, outage/retry and auditor restrictions), and workspace acceptance (17 views at 1440/1024/768/390/320 pixels, profile selection without identity change, knowledge search/empty/source detail, release/lineage views, missing-sample replay/reset, session draft persistence/escaping/clear, maintenance independence, device checklist, existing search/filter/CSV/dialog/density behavior). No hardware acceptance is implied.

### Catalog investigation extension

The authenticated planning catalog now supports combined text/category filtering, six quick filters with source-derived counts, component details with conditional/instrument/spare/safety boundaries, filtered CSV with explicit planning provenance, and navigation to device readiness and design sources. Asset details expose collapsible sensor-design context and a route to the corresponding BOM category. These references never establish a physical sensor assignment.

Chromium acceptance also verifies catalog filter intersections and empty/reset behavior, CSV scope/provenance, detail focus restoration, conditional-use wording, stale-detail removal and disabled actions during an API outage, filter-preserving retry, and the asset → component → device journey. No procurement, inspection, calibration, enrollment or hardware command is written by this interface.

### Persistent planning extension

The maintenance workspace now includes authenticated synthetic planning drafts, versioned creator edits, submission/withdrawal, independent admin approval/rejection, and durable decision history. See [maintenance planning contracts and boundaries](MAINTENANCE_PLANNING.md). Local review does not authorize operational work-order execution. A different admin account is required to review a creator's submitted request; administration does not bypass that rule.

The expanded local Python suite completed with 62 passed and 24 Python-browser cases skipped. Eight new API cases verify scope, CSRF, ownership, independent decisions, retry safety, stale/concurrent writes, approval invalidation, revocation and validation. Separate Chromium suites exercise the new planning service, existing workspace interactions and saved-report review against disposable databases.

## Remaining production work

Durable ingestion, enrolled device identities, actual sensor acquisition, central operational records, independent work-order decisions, enterprise identity, model release, grounded assistant services, recovery/load/security validation and physical commissioning remain required. A polished interface does not close these gates.

## Complete readiness coverage

See [the complete production readiness register mapping](PRODUCTION_READINESS.md). Every production-completion recommendation is represented, with no automatic completion inferred from existing prototype capabilities.

## Operations Desk refinement

The current shell uses compact page headings, persistent local quick access, a more prominent asset inspection path and metrics-first overview. Readiness includes a clickable status map for all 53 criteria and compact-list/detailed-card preferences. All original fields, target values, evidence/history, review controls, 30 hardware categories and 13 scope references remain present. Presentation preferences are local and confer no authority.
