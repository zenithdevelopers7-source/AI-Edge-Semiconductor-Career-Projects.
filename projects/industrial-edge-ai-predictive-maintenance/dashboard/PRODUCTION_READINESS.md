# Complete production readiness register

The Production readiness workspace represents every recommendation from the production-completion checklist. It is an authenticated, persistent evidence register, not automatic verification of equipment or a production certificate.

## Exact coverage

| Section | Included |
| --- | --- |
| Production requirements | All 18 areas |
| End-to-end demonstrations | All 15 scenarios |
| Measurable targets | 20 individual targets across all seven groups |
| Hardware | All 30 existing BOM planning categories, including conditional parts, instruments and spares |
| Release scope | 13 fields covering exact release/site/equipment/features/conditions, exclusions, support, risks, blocking defects and qualified acceptance references |
| Definition of completion | Defined deployed scope, all mandatory criteria, failure/recovery evidence, no blocking defects and dated responsible acceptance |
| Implementation priorities | All six next-priority groups retained |
| Conditional release statement | Clearly marked draft; usable only after real acceptance |

All criteria begin as Not started. Existing software capabilities are described as starting implementation boundaries and are never automatically accepted as production evidence. There is no not-applicable checkbox that silently removes a criterion.

## All 18 requirement areas

| Reference | Criterion | Completion / evidence |
| --- | --- | --- |
| REQ-01 | Approved scope and architecture | Define supported equipment, users, sites, operating conditions, features, system boundaries and responsible owners. Resolve conflicting active specifications. Approved requirements, architecture decisions, measurable acceptance criteria and an owner for every requirement. |
| REQ-02 | Verified physical hardware | Reconcile all 30 hardware categories with actual purchased parts, exact models, ratings, wiring, mounting, protection and installation records. Record conditional components, instruments and spares separately. Verified inventory, final diagrams, photographs, inspection records and qualified physical-safety acceptance. |
| REQ-03 | Reliable sensor acquisition | Acquire real acceleration, temperature, current and voltage measurements. Verify calibration, units, sampling rate, timing, sensor faults, clipping and missing readings. Repeatable real capture logs and calibration/quality results. Invalid readings remain unavailable rather than becoming misleading zeros. |
| REQ-04 | Device and asset identity | Register every device, sensor, gateway and monitored asset. Track firmware, configuration, boot identity, replacement history and approved assignments. Enrollment and replacement tests proving that observations belong to the correct physical equipment. |
| REQ-05 | Durable edge-to-server delivery | Implement persistent buffering, automatic retries, duplicate handling, content-conflict detection, bounded storage and recovery. Distinguish broker acceptance, edge persistence and central commit. Crash, restart, connection-loss, lost-response, disk-full, overflow, replay and reconciliation results. |
| REQ-06 | Production backend and storage | Connect authoritative APIs to durable operational records. Implement validated contracts, migrations, transactions, indexing, retention and controlled file/model storage. Preserve existing records during migration. API and concurrency tests, migration reconciliation, capacity measurements and rollback evidence. |
| REQ-07 | Production identity and security | Implement account provisioning, least privilege, privileged-account protection, session revocation, device credentials, encrypted transport, secret management and credential rotation. Unauthorized and cross-asset/site tests, expired/revoked credential tests, role-change tests and reviewed security findings. |
| REQ-08 | Fully connected dashboard | Connect fleet, assets, telemetry, devices, incidents, maintenance, models, reports and audit to authoritative services. Distinguish measured, simulated, replayed, stale, partial and unavailable data. Real-user task completion, permission checks, accessible controls/text, responsive browser tests and correct exports. |
| REQ-09 | Operational incident management | Implement creation, correlation, deduplication, assignment, acknowledgment, investigation, suppression with expiry, escalation, resolution, reopening and closure. Real observation-to-incident traces; duplicate and out-of-order inputs do not repeat operational effects. |
| REQ-10 | Complete maintenance workflow | Extend local planning to approved operational requests, technician assignment, execution evidence, independent verification and closure. Bind decisions to exact revisions and separate responsibilities. A complete real case through verified closure; self, stale, concurrent and revoked approvals are correctly denied. |
| REQ-11 | Validated predictive models | Obtain representative real operating data and credible labels. Prevent leakage, compare against a baseline, agree performance thresholds and document unsupported conditions. Independent real-recording evaluation, precision/recall, false-alarm results, uncertainty and reviewed model cards. Synthetic scores alone are insufficient. |
| REQ-12 | Controlled edge model deployment | Version features and model artifacts. Verify compatibility, runtime parity, resource use, inference timing, staged promotion, monitoring and rollback. Measured gateway results, approved release records and incompatible/corrupt-model plus rollback tests. |
| REQ-13 | Grounded AI assistance | For every promised AI capability, connect approved knowledge revisions with access restrictions, citations, uncertainty, abstention and human-reviewed proposals. Retrieval/access, unsupported-answer and injection tests; generated advice cannot grant permissions or bypass approval. |
| REQ-14 | Reproducible deployment | Establish controlled environments, pinned dependencies, release artifacts, configuration management, automated checks, secure deployment and migration procedures. Repeatable clean installation, upgrades, failed-upgrade handling and successful rollback. |
| REQ-15 | Monitoring and operational support | Monitor service health, sensor freshness, delivery lag, queues, resources, storage growth, model behavior and notification delivery. Assign support/escalation owners. Agreed targets met under realistic load and a supervised soak, with actionable alerts and response procedures. |
| REQ-16 | Backup and disaster recovery | Back up operational data, identity configuration, knowledge revisions, models and required configuration. Define acceptable data loss and restoration time. A clean restoration reconciles accounts, permissions, records, artifact references and pending deliveries within agreed targets. |
| REQ-17 | Data and knowledge governance | Establish ownership, permitted use, retention, exports, access restrictions and rights to datasets and operating documents. Approved policies and tested enforcement appropriate to the deployment. |
| REQ-18 | Final release acceptance | Close blocking defects, document limitations, train operators, assign ongoing maintenance and accept an exact release within a defined deployment scope. Dated acceptance from responsible engineering, physical-safety, security and operations reviewers. |

## All 15 demonstrations

| Reference | Criterion | Completion / evidence |
| --- | --- | --- |
| DEMO-01 | Real measurement journey | Trace sensor → acquisition device → edge gateway → central storage → dashboard with identity, units, timestamps and quality. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-02 | Network/backend outage | Demonstrate bounded local collection, visibly stale central data, automatic recovery and reconciled buffered records. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-03 | Device or gateway restart | Show a known recoverable outcome for previously acknowledged data across power/process interruption. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-04 | Duplicates and conflicting messages | Identical retries are idempotent; changed content under the same identity is rejected or quarantined without overwriting the original. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-05 | Sensor and timing faults | Missing, invalid, clipped, stale and ambiguous observations produce correct quality states, including clock/boot ambiguity. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-06 | Resource exhaustion | Full disks, queue overflow and corrupt storage produce explicit failures and documented recovery. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-07 | Unauthorized access | Incorrect, expired, revoked or wrongly scoped identities cannot ingest, read, approve or release protected resources. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-08 | Independent decisions | Self-approval, stale approvals, revoked rights and competing decisions have correct atomic outcomes. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-09 | Model failure and rollback | Incompatible or corrupt models cannot silently activate; accepted fallback and rollback work. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-10 | AI failure | Unavailable retrieval, malicious source content or insufficient evidence produces a bounded response or abstention. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-11 | Hardware replacement | Identity, calibration, assignments, revoked credentials and history remain correct after replacement. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-12 | Recovery | Failed deployment, migration and database loss can be recovered within agreed recovery targets. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-13 | Capacity | Realistic input rates, viewer counts, long-running operation and slow clients meet accepted limits. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-14 | Full maintenance case | Observation → incident → proposal → independent approval → technician evidence → independent verification → closure → audit trail. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |
| DEMO-15 | Provenance isolation | Synthetic and replayed data cannot impersonate measured equipment data or authorize real operational work. Dated real-deployment test procedure, conditions, observed results, logs/traces, exceptions and responsible reviewer. |

## All measurable targets

| Reference | Criterion | Completion / evidence |
| --- | --- | --- |
| TARGET-01 | Sampling rate (Measurement) | Agree the rate for each sensor/channel and acquisition mode. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-02 | Timing accuracy (Measurement) | Define timestamp accuracy, jitter and clock/boot handling. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-03 | Measurement quality (Measurement) | Specify calibration tolerances, clipping and validity criteria. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-04 | Collection capacity (Delivery) | Define sustained and peak acquisition/ingestion capacity. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-05 | Outage buffering (Delivery) | Specify the outage duration and bounded spool/storage budget. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-06 | Allowable data loss (Delivery) | Define loss tolerance and reconciliation across each acknowledgment boundary. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-07 | Detection latency (Detection) | Set maximum accepted observation-to-detection delay under stated load. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-08 | Alert latency (Detection) | Set detection-to-delivery/acknowledgment targets and escalation conditions. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-09 | Model performance (Models) | Agree precision, recall and other relevant thresholds on independent real data, with uncertainty. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-10 | False-alarm frequency (Models) | Define acceptable false alarms for actual operating conditions. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-11 | Availability (Recovery) | Agree service availability and the measurement window. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-12 | Recovery time (RTO) (Recovery) | Define and test the restoration-time objective. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-13 | Recovery point (RPO) (Recovery) | Define acceptable committed-data loss at restoration. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-14 | Supported devices (Scale) | Specify enrolled device count and transport mix. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-15 | Supported assets (Scale) | Specify monitored physical assets and simultaneous streams. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-16 | Supported sites (Scale) | Specify supported sites and isolation boundaries. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-17 | Concurrent users (Scale) | Specify concurrent viewers/operators and query workload. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-18 | Data retention (Data & resources) | Specify retention for telemetry, decisions, audit, models and knowledge. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-19 | Storage growth (Data & resources) | Measure growth and define capacity and alert thresholds. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |
| TARGET-20 | Operating resource budgets (Data & resources) | Agree and measure gateway/server resource and operating budgets. An agreed measurable value, operating conditions, accountable owner and test evidence showing the target is met. |

## Working controls and authority

- All supported authenticated local roles can read the current project register and export its complete authorized contents. Admin accounts edit evidence and scope; operators/auditors have read-only access. This is a local project register, not production multi-tenant IAM.
- Evidence fields include accountable owner, evidence/test references, conditions/notes, working status and an agreed target value for target criteria. Submission requires an owner and substantive evidence; measurable targets require a numeric agreement with units/context. Values are never invented from demonstration charts.
- Independent review requires a different admin from the record creator and latest editor, a decision note, a declared qualification/acceptance reference, the exact criterion revision and current bound release scope. Different accounts do not prove different people or professional qualification.
- Mutations require CSRF and fresh user/session/role checks under a serialized write transaction. Stale revisions and changed scope return conflicts; denied writes do not create partial review history.
- Editing accepted evidence clears its acceptance. Changing bound release/site/equipment/features/conditions/exclusions/support/risks/blocking-defect scope resets accepted and submitted evidence for fresh review. Historical evidence/reviews remain inspectable. Adding external sign-off references does not automatically invalidate an otherwise unchanged scope or commission equipment.
- Blocking safety/security defects are explicitly unknown/open/none. A complete recorded register requires all 53 recorded acceptances, all release fields and a declared clear blocking-defect state. Every API response still states production_ready=false, physical_acceptance_verified=false and equipment_authorized=false. Actual commissioning and qualified acceptance remain external facts requiring real evidence.
- Export includes all definitions, current records, target values, release scope/history, evidence/review histories, source catalog hash and all 30 planned hardware categories. References are plain text; no evidence file, credential or qualification is automatically verified or fetched.

## Interfaces

`GET /api/production-readiness` provides the complete register; `GET /api/production-readiness/export` exports all sections; item GET/PUT and independent-review POST manage revisions; release-scope PUT manages bound deployment scope. All endpoint mutations are audited.

## Validation and preservation

Seven isolated API cases verify exact counts/groups, authenticated read/export, roles/CSRF, evidence and target validation, revision conflicts, independent reviews, scope invalidation, current-role revocation and the non-certification boundary even when all 53 criteria have recorded acceptance. Separate Chromium acceptance exercises all six tabs, persistence, escaping, self-review prevention, stale forms, scope changes, target validation, complete export, read-only access, recovery, contrast and five viewport widths. The existing navigation suite now includes all 18 workspaces.

Startup adds four readiness tables without rewriting existing accounts, reports or saved maintenance planning. Installation takes a consistent local database backup first. Test users, accepted criteria and release claims are confined to disposable test databases; none are installed into the live local account database.
