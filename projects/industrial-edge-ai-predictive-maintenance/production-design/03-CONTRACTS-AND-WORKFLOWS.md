# 03 — Data Contracts, Identity, Workflows and Dashboard

**Status:** implementation specification candidate. Existing interfaces remain unchanged until versioned adapters and compatibility tests are built.

## 1. Canonical boundaries and migration

| Existing source | Observed capability | Target treatment |
|---|---|---|
| ESP32 serial V1 | Flat JSON, one report/s, no cryptographic board identity or boot UUID; m/s², V, mA and boolean sensor flags | Preserve legacy decoder; explicit gateway adapter with trusted attachment mapping and mA→A once |
| EA-22 candidate Telemetry V2 | Strict `2.0` / `telemetry.sample`, nullable SI channels, time/quality/session fields | Baseline raw/commissioning sample contract; retain its strict schema and format/semantic validation |
| EA-28–31 services | Synthetic-only fixed identities; test JWTs; localhost integration; EA-31 lacks durable upstream retry/conflict rejection | Keep as test evidence/harness, not production configuration or measured ingest |
| Dashboard synthetic ledger | Separate synthetic-only endpoint/store with `vibration_mm_s` | Keep research fixtures isolated; never rename this historical field to m/s² or ingest real acceleration into it |
| Dashboard browser fixtures | Static assets/signals/alerts; recent UI uses acceleration examples | Presentation reference only; migrate to bounded authorized operational queries |
| Saved offline comparisons | Immutable synthetic dataset/report hashes and local admin review | Import into an offline research domain with preserved IDs/provenance; not a deployable model |

One enrolled physical device has one active acquisition transport at a time. **Stage A:** serial-to-Pi adapter; publisher/service identity authenticates the Pi and separately attests the configured serial attachment. **Stage B:** reviewed firmware publishes directly with its unique device credential/boot UUID. Dual-run comparisons go into a shadow/evaluation stream, not duplicate production observations.

EA-22 V2 has `additionalProperties:false`. Firmware version, sampling context and new window metadata must live in a referenced acquisition manifest or an explicitly versioned new contract, not be silently inserted into V2. Freeze golden fixtures and old-reader behavior before changing a major schema version.

## 2. Contract families

| Contract | Producer → consumer | Required identity/provenance | Payload meaning |
|---|---|---|---|
| `telemetry.sample` / EA-22 `2.0` | Serial adapter or compatible device → edge/API | Enrolled device/asset/site, true or explicitly ambiguous boot/session, sequence, source type | Nullable instantaneous acceleration/temperature/voltage/current, per-channel quality and clock provenance |
| `edgeops.feature-window` / `1.0` (new) | Timed acquisition + feature engine → inference/API | Acquisition/session/config and source-window identity; source type; feature schema/hash | Window duration/rate/count/missingness/jitter, feature values/units, per-feature quality and source references |
| `edgeops.waveform-chunk` / `1.0` (new, bounded capture) | Acquisition → edge/object storage | Recording/boot/config/hash, channel order/units and source type | Bounded raw samples or object reference, encoding, 64-bit sample indices and integrity; not unbounded raw MQTT JSON |
| `edgeops.inference-result` / `1.0` (new) | Approved edge bundle → API | Source window + bundle + preprocessor + threshold/rule versions | Score, interpretation, decision/abstention, latency and required-feature quality |
| `edgeops.device-status` / `1.0` (new) | Device/edge supervisor → health domain | Registered principal/device, firmware/config and observation time | Last-seen, reboot, clock, queue/drops, sensor faults and resource status |
| `edgeops.ingest-receipt` / `1.0` (new) | Trusted edge/API → authorized sender | Event identity/hash, commit tier, receipt identity and timestamp | Edge-committed or central-committed acknowledgement; no motor action |
| `edgeops.workflow-event` / `1.0` (new) | Domain transaction/outbox → workers/UI | Entity/revision, actor, tenant/site, causation and policy version | State transition, reason and audit reference |

New families require actual JSON Schema/OpenAPI artifacts and positive/negative fixtures before implementation. They are specified here, not claimed as existing producers.

### Feature-window field specification

- `schema_name`, `schema_version`, `event_id`: exact contract family/version and stable logical identity.
- `site_id`, `asset_id`, `device_id`, `boot_id`: payload claims reconciled to authenticated transport and protected registry; tenant scope is attached server-side.
- `source_type`: measured/synthetic/replayed. Replays carry original recording/hash in a replay manifest, but cannot claim to be live.
- `recording_id`, `acquisition_manifest_sha256`, `feature_schema_sha256`: session provenance, unit/config definitions and extraction compatibility.
- `window_index`, `sample_start_index`, `sample_end_index`: bounded nonnegative indices; support 64-bit ranges in the new family and explicit limits in validators.
- `time`: nullable device observation times, monotonic bounds, gateway receipt, clock quality, offset/uncertainty where known. Gateway receipt is not silently a synchronized sample timestamp.
- `sampling`: configured/effective rate, window duration, expected/received/valid sample counts, jitter/missingness and per-channel age. Report observed facts; do not copy configured rate into a measured field.
- `features`: named nullable values in a declared feature schema; acceleration-derived RMS/peak/other features retain m/s² unless a validated different transform is explicitly named.
- `quality`: per-channel validity/calibration/clipping/gaps; overall eligibility is derived from each model's required-feature policy.
- `original_payload_sha256`, `adapter_version`, `firmware_release_id`: source/transformation lineage where available, with unknowns explicitly null/unverified.

Define maximum chunk/message bytes, field lengths, record counts, query ranges and permissible numeric domains in configuration with tested limits. Reject NaN/infinity and invalid timestamp formats. Quarantine unknown schema majors rather than guessing conversions.

### Semantic rules

1. Invalid/not-connected/stale-at-observation sensor channels are null; valid numeric zero remains a legitimate zero.
2. ADXL345 axes remain acceleration in m/s². Convert INA219 mA→A only at the declared adapter boundary; never twice.
3. Model eligibility lists its required channels and maximum ages. Missing required input means no score/abstention; partially valid telemetry remains inspectable.
4. Freshness at query time is computed separately from immutable acquisition quality. Historical valid records remain valid-at-observation even when their latest view becomes stale.
5. Freshness uses an explicit site/device publication policy and clock-quality bounds. Delayed backlog must not make an asset look newly healthy; keep `last_observed` and `last_received` distinct.
6. Firmware generates a true boot UUID for native mode. Current V1 has none: mark inferred/unavailable session identity, quarantine ambiguous resets, and never manufacture verified identity from an upload date.
7. Current 32-bit uptime wrap and restart are different conditions. Handle ordering using boot/session context and a monotonic extension policy; new waveform contracts support long-running sample indices. Changes beyond V2 limits require a version change, not truncation.
8. Raw windows, features and inference results retain different event types and causation. Never reconstruct FFT spectra from one instantaneous reading per second.

## 3. Identity, namespaces and replay

Adopt the EA topic convention `edgeops/v1/{site_id}/{device_id}/telemetry` for enrolled native devices, with separately defined status/edge-event/receipt topics. The topic's `v1` is independent of payload `2.0`. Serial-bridge principals have exact gateway-assigned topics and explicit attached-device mapping; they do not pretend to be the board's certificate.

Broker ACL grants each device only its own publication topics, and only its own receipt subscription if the application-receipt protocol is enabled. Edge consumers/publishers receive separate roles. Application receipts extend the earlier publish-only policy through a tracked ADR; they never open a generic command namespace. Use broker persistence, bounded message/session expiry and tested client behavior; no command/control topics are introduced.

Keep synthetic development/staging, measured laboratory operation, replay evaluation and an eventual measured pilot in separate broker/storage/identity configurations. A simulator cannot impersonate a measured device. Historical sensor recordings remain measured-origin evidence, but replay transport is explicitly replayed. Synthetic/replayed events cannot create measured-pilot maintenance orders by changing a payload flag.

Registry bindings include immutable instance/device IDs, approved site/asset, active transport, credential fingerprint/status, firmware/config version and installation dates. Changing a board requires enrollment and credential/history reconciliation. Alias legacy `motor-001`, `MTR-001` and lab fixture `motor-a` only through explicit mappings; they are not automatically the same physical asset.

## 4. Storage and idempotency

| Domain | Core records | Ownership/consistency |
|---|---|---|
| Identity/asset | tenants, sites, assets, device bindings, hardware instances, entitlements | Authoritative scoped mappings; history of installs/replacements |
| Acquisition | recording sessions, acquisition/calibration manifests, ingest keys and receipts | Preserve observation/provenance; no rewrite of source values |
| Time series | normalized samples/windows and downsampled aggregates | Supported TimescaleDB or partitioned PostgreSQL; bounded queries and retention |
| Artifacts | waveform objects, datasets, model bundles, SOP source files | Controlled object/file storage; DB references, hashes, revision and ACL |
| ML/research | experiments, comparisons, model candidates, validations, releases | Distinct report and deployment decisions; approved compatible bundle references |
| Maintenance | edge events, incidents, incident history, recommendations, work orders, approvals | Atomic version-bound transitions and append-only decision history |
| Operations | audit events, transactional outbox, delivery attempts, migration/evidence records | Restricted writes and monitored reconciliation/retention |

Logical ingest key: `(trusted tenant, device, verified boot/session, event_type, sequence-or-window-index)`. For unverified legacy sessions, use a separate commissioning policy and preserve ambiguity; do not claim global dedupe.

Calculate an immutable **measurement content hash** from source identity, observation/config, values, quality and provenance, using a defined canonical serializer. Exclude per-arrival gateway/API receipt timestamps and retry counters from that source-content hash; retain each receipt separately. A retransmission must not acquire a different logical measurement because its network arrival time changed.

- New key/hash: insert key, normalized record, receipt and domain-outbox intent in one DB transaction; return **201 only after commit**.
- Existing key, identical content hash: return **200** with the original record/commit reference; no repeated domain effect.
- Existing key, different hash: **409 conflict**, quarantine/audit and no overwrite. This closes an explicit EA-30/31 gap.
- Invalid/unsupported payload: **400/422** with safe reason code; unauthorized mapping: **403**; missing/invalid authentication: **401**; quotas: **429**; unavailable dependency: retryable **5xx**.
- Asynchronous **202** is allowed only after a separately specified durable inbox commit with a receipt/status API; never use it for an in-memory list.

Keep the dedupe key table independent of time-partition/hypertable uniqueness constraints. Its retention must cover the accepted replay horizon; late replay after key expiry needs a defined reject/archive policy. Deleting old keys while accepting unlimited old retries invalidates dedupe guarantees.

An outbox record and its originating domain update commit together. Workers claim bounded batches, retry transient failures and dedupe effects with stable event IDs; poisoned records enter a visible dead-letter/review state. Operator replay is authorized, rate-limited and audited.

## 5. Operational API surface

These are target routes, not a claim that the current dashboard serves them.

| Method / route | Principal | Preconditions and response semantics |
|---|---|---|
| POST `/api/v1/ingest/telemetry` | Enrolled edge service | Schema/registry/session/content validation and durable key/hash contract |
| POST `/api/v1/ingest/edge-events` | Scoped inference service | Approved bundle/source-window references and result quality |
| GET `/api/v1/ingest/receipts/{id}` | Sender scoped to event | Receipt/commit tier without unrelated device disclosure |
| GET/POST `/api/v1/assets` | Scoped reader / asset admin | Asset and physical/synthetic classification; registry version |
| GET `/api/v1/assets/{id}/telemetry` | Authorized asset reader | Required start/end, signal/unit, resolution, point cap and provenance |
| GET `/api/v1/assets/{id}/health` | Authorized asset reader | Separate connection, freshness, sensor quality and model/condition states |
| GET `/api/v1/devices/{id}/diagnostics` | Scoped operator/engineer | Last observation/receipt, firmware/config, queue and sensor state |
| GET/POST `/api/v1/incidents` | Reader / deterministic domain service | Cursor/severity/state filters; correlation not arbitrary client state edits |
| POST `/api/v1/incidents/{id}/acknowledge` | Scoped operator | Expected revision + idempotency key + reason; audit commit |
| POST `/api/v1/recommendations` | Technician or constrained draft service | Evidence references and revision; no approval privilege |
| POST `/api/v1/work-orders/{id}/submit` | Scoped creator/technician | Immutable submitted revision and required evidence |
| POST `/api/v1/work-orders/{id}/approve` | Independent approver | Current identity/grants, distinct creator, submitted revision, atomic audit |
| POST `/api/v1/work-orders/{id}/reject` | Independent approver | Same authorization/version checks, required reason |
| POST `/api/v1/work-orders/{id}/transition` | State-authorized human | Allowlisted operation, current revision, execution/verification evidence |
| GET `/api/v1/experiments` | Research-authorized reader | Provenance/split/metric/artifact summary; no implicit field-performance ranking |
| POST `/api/v1/model-releases/{id}/approve` | ML release approver | Validated candidate bundle; separate release workflow and deployment gate |
| POST `/api/v1/assistant/ask` | Scoped user through BFF | Bounded authorized evidence, SOP revisions, citations or abstention |
| GET `/api/v1/audit` | Scoped auditor/admin | Authorized filters, cursors, integrity/retention context and safe exports |
| GET `/api/v1/stream/events` | Scoped human session | Authorized event hints; reconnect cursor/heartbeat plus authoritative refetch |

All mutations require expected revision where relevant, idempotency keys, current server-side scope checks and CSRF protection for browser cookie sessions. Reusing an idempotency key with another body is a conflict. Do not expose sensitive existence through cross-tenant error messages. Publish schemas and generated client types in CI; version incompatible contract changes.

## 6. Domain state machines

**Incident:** `open → triaged → acknowledged → investigation → resolved → closed`, with policy-bound `suppressed` (reason/expiry), escalation and reopening events. `sensor_fault`, `data_quality`, `connectivity` and `anomaly` are incident families, not interchangeable evidence of a mechanical failure. Correlate by asset/family/time/policy version; enforce one active correlation record through a transaction-safe constraint/lock.

**Work order:** `draft → submitted → approved | rejected`; `approved → in_progress → completed → verified → closed`; cancellation follows explicit state/role policy. Rejection returns a new editable draft revision when revised. A material edit to an approved proposal invalidates approval and requires resubmission. Technician completion is not independent verification. Capture evidence and separate verifier where required.

Approval transaction checks authenticated immutable actor ID, current entitlements, site/asset, submitted state, expected revision, creator≠approver, decision reason, idempotency key and required evidence. Update state, insert approval/history/audit and create the outbox event atomically. Two simultaneous decisions cannot both win. A replay returns the prior compatible outcome. A role revoked between page load and action must be denied.

**Offline report:** pending/approved/rejected means only that a report was reviewed. Existing local admin reviews may remain labeled legacy offline reviews; they are not independent industrial signoffs.

**Model release:** candidate/evaluated/staged/release-approved/active/retired; independent approval and activation checks operate on a frozen compatible bundle. A model-release decision is neither a work-order decision nor electrical authorization.

## 7. Role and permission design

| Role | Scope | Allowed actions | Explicit limitation |
|---|---|---|---|
| Viewer | Assigned site/assets | Read authorized operational evidence | No workflow writes |
| Operator | Assigned site/assets | Read, acknowledge, triage and create drafts by policy | Cannot approve own request |
| Technician | Assigned work/assets | Investigate, edit drafts, submit, record completion evidence | Cannot self-verify where separation applies |
| Approver | Explicit workflow grant/site | Approve/reject submitted current revisions | Distinct from creator; no equipment control |
| Auditor | Authorized audit scope | Read history/evidence and permitted exports | No operational mutation |
| Asset/device administrator | Registry scope | Enroll, bind, revoke and maintain configuration under change policy | No implicit maintenance/model approval |
| ML reviewer/release operator | Model/environment scope | Review and promote eligible bundles with release gate | Cannot bypass evaluation/signature/rollback policy |
| Advisory agent | Calling-user evidence scope | Read typed evidence and draft a proposal | No approval, role grant, shell, control or model deployment |
| Edge/inference service | Enrolled device/bundle scope | Ingest its telemetry/results | No unrelated data reads or human actions |

Administrative access must not silently bypass separation of duties. Emergency/break-glass access, if later required, is a distinct bounded policy with explicit activation and independent audit; it is not a default UI checkbox.

## 8. Complete production workspace design

The current 12 sections are a navigation starting point. The target expands domain pages/subpages where needed; production completeness is functional coverage, not a fixed count of tiles.

| Workspace | Key screens and actions | Authoritative data and required UX states |
|---|---|---|
| Access | Sign-in, session expiry, access denied, approved account recovery | Identity/session service; distinguish unavailable IAM from wrong credentials |
| Fleet | Overview, sites, health/quality/freshness filters | Asset/health API; no fabricated uptime, failure risk or unknown-as-healthy |
| Assets | Registry, asset detail, sensor mapping, installation/calibration history | Registry and observations; physical/synthetic labels and unavailable channel states |
| Telemetry | Multi-signal trend, bounded range/resolution, data table/CSV, quality overlays | Historical query API; units, observed/received time, gaps and clock quality |
| Device/edge health | Enrollment, firmware/config, broker/spool/model and resource diagnostics | Registry + status API; heartbeat is not proof every sensor works |
| Incidents | Queue, detail timeline, assignment, acknowledge, suppression, evidence | Versioned incident API; race conflicts and current permissions |
| Maintenance | Draft/recommendation, submitted review, independent decision, work-order board, execution/verification | Workflow API; disabled actions explain actual missing prerequisites |
| AI assistant | Case-linked questions, cited SOP passages, uncertainty, editable proposal | Authorized RAG service; clear unavailable/abstention, no implied live diagnosis |
| Knowledge | Approved documents/revisions, ingestion review, applicability and access | Document manifests/ACL; superseded source visibility and traceable citations |
| Models/research | Datasets, comparison details, split quality, model card, release review and rollback | Separate experiment and model-release services; offline scores not field accuracy |
| Hardware | 30-category BOM, instances, procurement, inspections, spares and replacements | Hardware registry; planned/received/commissioned are distinct |
| Simulation/replay | Scenario catalog, manifests, evaluation runs and origin filter | Isolated simulator/evaluation services; no measured-pilot workflow effects |
| Security/audit | Session, grants, decisions, tamper evidence, authorized exports | Identity/audit services; actor/reason/revision/policy and denial visibility |
| Governance/operations | Gates, risks, release status, recovery evidence and owner/runbooks | Evidence/operations register; no automatic signoff from test counts |
| Reports | Operational evidence exports, offline experiment reviews and maintenance reports | Scoped query/report services; include units, filters, provenance, times and revisions |
| Settings | Site-approved limits, notifications, display/timezone preferences | Versioned config by role; local display preferences distinguished from operational policies |

Every data-backed page specifies loading, empty, denied, unavailable, stale, partial/degraded and success states. Failed fetches do not leave unlabeled stale numbers. Native dialogs/keyboard focus, clear labels, contrast, reduced motion, mobile navigation and bounded table scrolling are shared requirements. Backend authorization remains effective when buttons are hidden or altered.

SSE carries authorized change hints and sequence/cursor context; a disconnected client visibly degrades and refetches current authoritative state on reconnect. A working API chip is service connectivity, not proof of a live physical signal. Exports apply current server scope/filters and retain origin and units.

## 9. Acceptance narratives

**Real measured path:** commissioned sensor observation → valid source/session/config → durable edge receipt → approved scoring/rule result → committed central record → correlated incident → cited or human-written inspection proposal → independent authenticated decision → technician evidence → verifier closure → exportable audit trace. Do not manufacture an anomaly if the detector does not flag a safe operating-state change.

**Replay path:** authorized recorded dataset → isolated replay manifest → same validation/feature/workflow software with replay provenance → reproducible evaluation. Its outputs cannot be relabeled measured-live or create real pilot orders.

**Failure path:** kill/restart edge/worker/API, lose network or corrupt a bundle → explicit quality/freshness/backlog state → bounded recovery → key/hash reconciliation → no duplicate work order or falsely healthy status. Store exact software/hardware/config identity and observed losses.
