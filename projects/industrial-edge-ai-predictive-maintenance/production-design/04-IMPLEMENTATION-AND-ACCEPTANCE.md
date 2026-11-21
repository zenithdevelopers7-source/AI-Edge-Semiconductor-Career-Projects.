# 04 — Implementation Backlog, Requirements and Release Acceptance

**Purpose:** turn the consolidated design into buildable vertical slices. **Status:** implementation plan, not completed production work. No hardware or operational configuration is changed by authoring this package.

## 1. Target repository organization

Create new production modules alongside the working `dashboard/`, source firmware and `enterprise-architecture/` lab. Avoid a destructive directory rewrite.

```text
production-design/                 this reviewed design baseline
platform/
  contracts/                       schemas, OpenAPI, fixtures and generated clients
  api/                             FastAPI domain modules, policy and migrations
  workers/                         incident/outbox/notification/retrieval jobs
  web/                             Next.js/TypeScript workspace and BFF
edge/
  acquisition-adapter/              serial compatibility and identity mapping
  agent/                           durable inbox/outbox, broker client and diagnostics
  features/                        deterministic feature pipeline
  inference/                       compatible approved bundles and fallback
hardware/
  manifests/                       exact BOM instances, wiring and commissioning evidence
  firmware/                        reviewed native acquisition/MQTT implementation
ai/
  datasets/ training/ evaluations/  provenance, split manifests, models and parity
  knowledge/ advisory/             approved SOPs, retrieval and bounded proposal graph
simulation/                        isolated deterministic replay/fleet/scenarios
infra/
  compose/ identity/ monitoring/    environment manifests and deployment/runbooks
  backups/                         restore scripts and redacted evidence, not private backups
```

These are proposed paths. No empty directories are presented as implemented services. Keep dependency locks, supported runtime combinations and container digests under the owning module; actual choices are validated during each slice.

## 2. Dependency-ordered delivery backlog

| Slice | Deliverable and owner role | Depends on | Required exit evidence |
|---|---|---|---|
| B0 — Design reconciliation | Architect/data/firmware owners confirm this baseline, exact requirements, source status and migration ADRs | Existing documents/code | Source manifest, decisions with owners, compatibility fixtures and unresolved-input register |
| B1 — Physical inventory and sensor bring-up | Hardware/embedded: all 30 categories reconciled, actual modules/pins/ratings, sensor-only capture | B0; actual parts | Instance register, sensor-only diagram/photos, calibration/validity/timing logs; motor remains separately gated |
| B2 — Contract and registry foundation | Backend/data/security: canonical contracts, device/site/asset bindings, scoped access | B0 | Strict positive/negative schema and semantic tests, source-unit mapping and migration compatibility |
| B3 — Reliable edge vertical slice | Edge/platform: serial adapter first, broker identity, durable inbox/outbox, conflict-aware upstream ingest | B1 sensor path or synthetic fixtures; B2 | Kill/restart/lost-response/outage tests, explicit broker/edge/central receipt traces, bounded overflow and replay |
| B4 — Timed native firmware | Embedded/security: nonblocking sampling, boot/config identity, native TLS MQTT, enrollment | B1/B2; B3 acceptance model | Measured rates/jitter, partial-sensor behavior, credential/ACL/clock tests and transport-cutover evidence |
| B5 — Central application foundation | Backend/platform: PostgreSQL migrations, scoped APIs, controlled objects, identity and audit | B2; integrates B3 | Authentication/scope tests, durable transaction and rollback/restore checks, no synthetic-to-measured impersonation |
| B6 — Deterministic incidents/work orders | Domain/backend: correlation, policies, versioned independent approval and verification | B5; B3/B4 observation stream | One-event/one-incident effect, concurrent decisions, self/stale/revoked approval denial, completion/verification trace |
| B7 — Contract-backed web workspace | Frontend/product: fleet, asset, telemetry, device, incidents, orders, reports and audit | B5/B6; parallel fixture-driven components | Responsive/browser/keyboard tests, freshness/quality/export states and real API workflow evidence |
| B8 — Measured edge intelligence | ML/edge: healthy sessions, baselines, feature version, justified ONNX bundle and release | B1/B3/B4 + qualified guarded runs | Leakage audit, same-holdout baseline comparison, parity, measured Pi resource/timing and rollback |
| B9 — Knowledge/advisory integration | AI/data/security: authorized SOP lifecycle, citations, abstention and draft-only tools | B5/B6; reviewed SOP rights | Retrieval/ACL/revision tests, injection and unsupported-diagnosis tests, human-approved proposal trace |
| B10 — Fleet/recovery/release | Operations/security/QA: isolated simulator, drift, load/soak, operational recovery and deployment acceptance | Applicable B3–B9 scopes | Reproducible load/failure/restore/rollback evidence, resolved risks, named support and signed release record |

UI work may proceed against approved fixtures in parallel, but a visual page cannot satisfy its operational exit criterion until the authoritative API and workflow exist. A safe rules-based measured pilot can be scoped before ONNX/RAG if explicitly accepted; it must not advertise unimplemented intelligence. Completing the full proposed product requires the remaining capabilities and their own evidence.

## 3. Requirements traceability

EA-01 and EA-09 reuse some FR numbers with different wording. For this consolidation, preserve original IDs with qualified references; use EA-09 as the verification matrix and keep EA-01 as the capability source. Do not silently reassign IDs in historical documents.

| Design requirement | Source mapping | Owning slice | Acceptance scenario |
|---|---|---|---|
| PDR-01 — Hardware category and instance traceability | Hardware register, Phase 01, EA-19 | B0/B1 | All BOM-01..30 have role, installation condition and test; no purchase/commissioning state without evidence |
| PDR-02 — Scoped asset/device enrollment | EA-09 FR-01, NFR-04 | B2/B5 | Authorized enroll succeeds; foreign site/device claims fail; replacement retains history |
| PDR-03 — Traceable valid/partial observations | EA-09 FR-02, EA-22, C-01/C-07 | B1/B2/B4 | Golden V1 mapping, null invalid fields, legitimate zeros retained, mA→A once, clocks/session ambiguity explicit |
| PDR-04 — Observable durable delivery | EA-09 FR-03, NFR-02; EA-31 gaps | B3 | Broker receipt not central success; crash/restart/response loss and overflow have reconciled outcomes |
| PDR-05 — Immutable data origin | EA-09 FR-04, Phase 07 | B2/B5/B7/B10 | Synthetic/replayed record cannot impersonate measured device or create measured-pilot orders |
| PDR-06 — Evaluated anomaly interpretation | EA-09 FR-05, NFR-05; Phase 03 | B8 | Independent session splits, identical holdouts, bounded missing-input behavior and compatible bundle rollback |
| PDR-07 — Idempotent incident correlation | EA-09 FR-06, Phase 04 | B6 | Duplicate/out-of-order events do not create repeated incidents/work orders; policy changes are attributable |
| PDR-08 — Authorized cited advice | EA-09 FR-07; Phase 06 | B9 | Correct eligible SOP revision, no unauthorized excerpts, missing evidence abstains, injection cannot grant tools |
| PDR-09 — Independent version-bound approval | EA-09 FR-08; EA-24 ZT-12..15 | B6 | Self/stale/revoked/concurrent/replayed decisions have deterministic denied/idempotent outcomes |
| PDR-10 — Auditable, recoverable decisions | EA-09 FR-09, NFR-03 | B5/B6/B10 | Trace source→decision; restricted audit mutation; clean restore reconciles data, object refs and outbox |
| PDR-11 — Independent physical protection | EA-09 FR-10; R-02/R-03 | B1 + actual qualified review | Exact power/measurement/driver/guard design and independent disconnect acceptance before energized runs |
| PDR-12 — Secure private transport | EA-09 NFR-01; EA-24 ZT-01..08 | B3/B4/B5 | Invalid/expired/revoked identity, wrong host/topic/site and plaintext fallback fail closed |
| PDR-13 — Usable evidence-first workspace | EA-09 NFR-06; 15-screen reference; UI review | B7 | Keyboard and mobile task completion, no unknown-as-healthy, clear stale/partial/denied/export behavior |
| PDR-14 — Controlled release and operations | Phase 08; EA-06/14/21 | B10 | Pinned manifests, scanners, staged deployment, monitoring owners, restore and rollback under accepted targets |

Every Must requirement maps to an actual observed result and evidence record before its acceptance state changes. Traceability coverage is not test execution.

## 4. Critical cross-system test matrix

| Test ID | Scenario | Required invariant / observed evidence |
|---|---|---|
| E2E-01 | Motor-disconnected sensor-only acquisition | Measured source, actual timing, valid or explicit null channels and physical instance/config references |
| E2E-02 | Qualified guarded baseline run | Approved physical scope and real sensor-to-dashboard trace; no unsupported fault diagnosis |
| E2E-03 | Serial/native cutover and board replacement | One active live transport, correct identity/boot history and no duplicate physical stream |
| E2E-04 | Duplicate identical source event | Stable central record and no repeated domain effects, including lost HTTP response retry |
| E2E-05 | Same key, modified measurement | 409/quarantine; original unchanged; conflict reason/audit preserved |
| E2E-06 | Edge process killed before/after durable acceptance | Receipt/spool/broker state reconciles; no invented commit and measured loss, if any, recorded |
| E2E-07 | Backend unavailable, sensor→edge healthy | Local bounded collection/scoring, stale central state, automatic idempotent recovery |
| E2E-08 | Device/Wi-Fi/Pi unavailable | No fresh-data inference claim; separate heartbeat/observation freshness states |
| E2E-09 | Disk full, corrupt spool/model, queue overflow | No silent success; reserved recovery capacity, explicit counters and qualified fallback |
| E2E-10 | Sensor invalid/clipped/old; clock or uptime wrap | Required-feature abstention, legitimate partial data retained, no epoch/boot confusion |
| E2E-11 | Identity/topic/tenant/SOP scope attack | No unauthorized ingest/read/excerpt or domain effect; useful redacted denial evidence |
| E2E-12 | Two approvers, stale edit, self-approval or role revocation | Atomic version/policy check and exactly one compatible state transition |
| E2E-13 | Model release/report review confusion | Report approval cannot deploy; only approved compatible signed/verified bundle can activate |
| E2E-14 | Malicious SOP/agent response or unavailable retrieval | No new tools/privileges; cited supported draft or explicit abstention |
| E2E-15 | SSE reconnect, slow viewer, long telemetry range | Bounded queues/query points; refetch authoritative state and visible freshness |
| E2E-16 | Synthetic fleet and measured data/replay | Identity/environment isolation and provenance persist into reports/exports/orders |
| E2E-17 | Deployment/DB migration failure and clean restore | Login/entitlements, records, object hashes, bundle refs and pending effects reconcile |
| E2E-18 | Spare replacement and manual protection inspection | New board/calibration identity, old credential revoked, hardware inspection evidence retained |
| E2E-19 | Load and supervised soak | Actual input rate/viewer count, timings, resource/storage growth, drops and recovery logs; no assumed capacity |
| E2E-20 | Full maintenance case | Observation→incident→proposal→independent approval→technician evidence→verification→closure→audit trace |

These are required future tests. The existing 132 recorded enterprise-lab results and current dashboard checks do not automatically pass this matrix.

## 5. Design and release gate crosswalk

The repository has two different G-number systems. Keep them qualified rather than confusing Phase 08 hardware G1 with enterprise architecture G1 requirements.

| Design/release area | Architecture gates (EA-21) | Phase 08 gates | Closure evidence |
|---|---|---|---|
| Scope/requirements/architecture | AR-G0/G1/G2 | Supports all release gates | Actual accepted scope, PDR mappings, contracts, ADRs and assigned owners |
| Hardware/physical safety | AR-G4b | REL-G1 | Exact rated design, installation and qualified independent review |
| Connectivity and ingestion | AR-G2/G4a/G5 | REL-G2/G4 | Enrolled identities, durable replay/conflict handling, central data/migrations |
| Models/AI advice/fleet | AR-G3 | REL-G3/G6/G7 | Real labeled/healthy-session evaluation, parity/benchmark, RAG and replay evidence |
| Workflow and audit | AR-G2/G4a | REL-G5/G8 | Scoped independent decisions and integrity/negative tests |
| Operations and deployment | AR-G5/G6 | REL-G8/G9 | Supported versions, security review, monitoring, clean restore and rollback |
| Evidence and presentation | AR-G6 | REL-G10 | Dated release record and accurate demo/limitations, not a certification claim |

Current disposition: new design authored; no architecture or physical signoff is created by this document. Production acceptance requires all applicable Must gates, accepted residual risks and named operational ownership. A single-person self-assessment may be useful but must not be labeled an independent review.

## 6. Migration and change protection

1. Preserve the working dashboard, existing SQLite accounts/audit and experiment directories; keep backups and source/version references.
2. Freeze current API behaviors and golden synthetic fixtures, including the historical mm/s research ledger. Do not convert those records into measured acceleration data.
3. Add production modules/contracts independently. Maintain a compatibility adapter/read-only historical report view instead of repurposing lab-only ingress or fixture identities.
4. Build trusted asset/hardware identity mappings. Never infer physical purchases from static catalog labels or cart entries.
5. Introduce PostgreSQL through explicit migration scripts and reconciliation reports. A migration is complete only with counts/hash/references and rollback evidence.
6. Enroll real OIDC subjects through verified identity binding and explicit authorization. Matching an email string is not enough to transfer an old local admin role. Expire/recreate sessions through the new provider; do not copy test cookies or signer secrets.
7. Move web pages by vertical workflow against generated clients; preserve useful UX and existing browser acceptance as regression requirements.
8. Cut over one commissioned rig in an isolated measured environment, retain rollback to the last compatible release, and record actual observation quality before broader rollout.

## 7. Inputs needed before the design can be frozen for deployment

| Input | Why required | Current handling |
|---|---|---|
| Exact purchased motor/driver/sensor modules and electrical ratings | Final circuit, measurement suitability and protection | Open; category-level design only; do not choose fuse/wire/current values by guess |
| Actual received/installed inventory | Procurement and commissioning truth | All 30 planned categories mapped; no ownership inferred |
| Named physical/security/operational reviewers | Genuine acceptance and residual-risk ownership | Roles specified; no invented signatures |
| Pilot users/sites, operating duty and expected outage | Identity scope, capacity, spool and availability | One-rig baseline and explicit test assumptions |
| Approved data location/classification/retention | Storage/export/backup and permitted LLM/SOP processing | Deployment-specific decision, no legal compliance assertion |
| SLO/RPO/RTO and cost constraints | Operational acceptance and host sizing | Measure baseline, propose business-supported targets, then test |
| Licensed SOPs and real recording/label evidence | Grounded guidance and credible model evaluation | Missing evidence stays explicit; synthetic tests remain separate |

These inputs do not prevent a concrete architecture proposal or software-only contract work. They prevent pretending an unverified physical installation or production approval already exists.

## 8. Immediate next buildable step

Implement **B2 + the software-only part of B3**: approved contract fixtures, registry mapping, durable edge inbox/outbox and central key/hash conflict handling, using synthetic identities in an isolated test environment. This closes the reliability gap explicitly identified by EA-31 and creates the authoritative data path the production UI needs. Physical bring-up is a separate B1 track when actual hardware and reviews are available. Do not continue with cosmetic UI-only milestones as a substitute for this foundation.
