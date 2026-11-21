# 05 — Source Review, Conflicts and Evidence Register

**Review date:** 19 November 2026. This is a consolidated source/design review, not a new run of the historical hardware, broker, security or load tests.

## 1. Review scope and precedence

Reviewed all 48 existing project Markdown documents, the portfolio root overview as context, the embedded acquisition/serial source, strict V2 contract, policy and MQTT/HTTP durability source, and the current dashboard/research behavior. Recorded lab evidence was checked separately, including UTF-16 PowerShell logs. Seven historical HTML prototypes and the archived 15-screen reference guide were catalogued/read for product navigation context. Images and packaged prototypes are visual references, not runtime assurance.

The source checkout identifies Git head `25f943a`; the recent saved-comparison and workspace changes were local extensions, not a pushed production release. Full file hashes are recorded in [source-manifest.json](source-manifest.json), so the review is not falsely bound solely to an older commit. This package does not claim independent review, new physical tests or deployment acceptance.

Evidence precedence: exact scoped source and execution artifact → current consolidated design/review → dated implementation guides → older product overview prose. A recorded test result can supersede an old “not executed” label only for that exact test scope, not for the production gate.

## 2. Reconciliation and conflict disposition

| ID | Finding | Consolidated disposition |
|---|---|---|
| REC-01 | Full 30-category hardware register versus dashboard's 14 grouped names/16 generic slots | BOM-01..30 design categories; preserve legacy aliases; actual purchases/instances separately verified |
| REC-02 | Cart counter/selected connector versus physical ownership | Cart/selection is not paid/delivered/commissioned inventory; exact models and ratings remain open |
| REC-03 | Flat serial V1 versus proposed nested contracts | Preserve V1 and use explicit adapter; EA-22 V2 is the raw candidate, new feature/window families are separately versioned |
| REC-04 | Current 1 Hz acceleration reads versus high-rate RMS/FFT expectations | No existing high-rate or spectral claim; timed acquisition/window pipeline is a separate firmware/feature slice |
| REC-05 | m/s² firmware versus mm/s synthetic dashboard ledger | Keep physical units unchanged; historical synthetic velocity-like fixtures do not become measured acceleration |
| REC-06 | Device name conflates board and motor; V1 has no verified boot identity | Enrolled hardware/device/asset mapping, true native boot UUID; serial identity remains gateway-attested/ambiguous as applicable |
| REC-07 | Serial gateway and direct ESP32 MQTT both appear in diagrams | Commissioning path and target path are staged alternatives; one active live transport per enrolled device |
| REC-08 | MQTT PUBACK versus durable downstream acceptance | Separate broker/edge/central receipts; durable inbox/outbox, bounded backpressure and automatic retry required |
| REC-09 | EA-30/31 duplicate same key/different content treated as duplicate | Canonical measurement hash, 409 conflict and no overwrite; receipts excluded from immutable source-content hash |
| REC-10 | Lab synthetic JWT/fixed registry/plain loopback HTTP versus enterprise identity | Preserve lab harness restrictions; production uses separately enrolled service/device/human identities and protected transport |
| REC-11 | Current SQLite dashboard versus PostgreSQL/TimescaleDB/Next.js target | Modular production application and staged API/web migration; preserve local accounts/reports and compatibility evidence |
| REC-12 | Current report review could be mistaken for release or work-order approval | Separate report, maintenance and model-release domains, rights, revisions and audit events |
| REC-13 | Multiple incident/work-order state diagrams | Canonical distinct incident and work-order machines in chapter 03; source states mapped during migration |
| REC-14 | EA-01/EA-09 FR labels and two G-number schemes differ | Qualified source references; new PDR requirements and AR-G / REL-G gate crosswalk |
| REC-15 | Several architecture/README status labels predate executed evidence/UI changes | Preserve historical text; source register explicitly records later scoped results and current local extensions |
| REC-16 | “All hardware” includes conditional buck/shifter, instruments and spare kit | Trace use across installed/commissioning/conditional/spare lifecycle roles; never force an incompatible circuit |
| REC-17 | Motor-driver/supply variants and transient protection are not fully specified | Exact-part electrical review; no automatic TB6612/3 A/5 A approval or topology-independent flyback wiring |
| REC-18 | Existing source includes 30 numbered EA prose files, with EA-23 represented by test/evidence | Do not invent a missing prose document; keep recorded contract evidence and test source linked |
| REC-19 | Historical 15-screen references versus current 12 sections | Cover every required operational capability with pages/subpages, not a cosmetic fixed page count |

## 3. Recorded enterprise evidence (not re-executed here)

| Milestone | Recorded result | Proven scope | Does not establish |
|---|---|---|---|
| EA-23 | 18 tests, OK | Local V2 schema/fixture checks | Real sensor acquisition/transport |
| EA-25 | 34 tests, OK | Offline synthetic authorization predicates | Real OIDC, deployed role isolation or concurrency |
| EA-27 | 24 tests, OK | In-memory multi-boundary sandbox | Real broker/transport/database |
| EA-28 API | 14 tests, OK | In-process FastAPI and test JWT | Network HTTP/TLS and enterprise IAM |
| EA-28 broker | 3 tests, OK | Local Mosquitto mTLS/ACL and PUBACK assertions | Full credential lifecycle or production PKI |
| EA-29 | 12 tests, OK | Local MQTT into TestClient/in-memory API | Durable end-to-end transport |
| EA-30 | 15 tests, OK | Separate loopback HTTP API and SQLite restart/dedupe | Payload-conflict rejection or actual OIDC |
| EA-31 | 12 tests, OK | Local MQTT→independent HTTP→SQLite; manual replay | Automatic spool/retry, measured hardware or production approval |

The stored records total 132 scoped checks across different suites/versions; they are not 132 production acceptance tests. Their exact paths/hashes appear in the manifest. Authoring-time “not executed” labels in earlier prose are therefore stale for these recorded runs. Later dashboard validation reported 54 non-browser checks and two Chromium acceptance flows; the existing 24 Python Playwright cases were locally skipped when their dependency was absent. Those dashboard checks are a different scope and must not be presented as a single comprehensive hardware-to-cloud test count.

## 4. Existing Markdown source register

| Source path | Review focus | SHA-256 prefix |
|---|---|---|
| [dashboard/README.md](../dashboard/README.md) | Current local application behavior, evidence and known production gaps | `fb082a14fed6` |
| [dashboard/UI_UX_REVIEW.md](../dashboard/UI_UX_REVIEW.md) | Current local application behavior, evidence and known production gaps | `949baa41311c` |
| [enterprise-architecture/01-ENTERPRISE-ARCHITECTURE-CHARTER.md](../enterprise-architecture/01-ENTERPRISE-ARCHITECTURE-CHARTER.md) | Architecture, contract, risk, policy or integration requirements | `ab57b5d67aa0` |
| [enterprise-architecture/02-SOLUTION-ARCHITECTURE.md](../enterprise-architecture/02-SOLUTION-ARCHITECTURE.md) | Architecture, contract, risk, policy or integration requirements | `8e2a257f0764` |
| [enterprise-architecture/03-SYSTEM-INTEGRATION-DESIGN.md](../enterprise-architecture/03-SYSTEM-INTEGRATION-DESIGN.md) | Architecture, contract, risk, policy or integration requirements | `4bd606be1616` |
| [enterprise-architecture/04-AI-AND-AGENT-ARCHITECTURE.md](../enterprise-architecture/04-AI-AND-AGENT-ARCHITECTURE.md) | Architecture, contract, risk, policy or integration requirements | `6e5f4d899944` |
| [enterprise-architecture/05-SECURITY-GOVERNANCE-AND-SAFETY.md](../enterprise-architecture/05-SECURITY-GOVERNANCE-AND-SAFETY.md) | Architecture, contract, risk, policy or integration requirements | `637a68f4d781` |
| [enterprise-architecture/06-QUALITY-OPERATIONS-AND-COST.md](../enterprise-architecture/06-QUALITY-OPERATIONS-AND-COST.md) | Architecture, contract, risk, policy or integration requirements | `492e5ca7f7c4` |
| [enterprise-architecture/07-ARCHITECTURE-DECISIONS.md](../enterprise-architecture/07-ARCHITECTURE-DECISIONS.md) | Architecture, contract, risk, policy or integration requirements | `dbac65ad701d` |
| [enterprise-architecture/08-DESIGN-REVIEWS-AND-READINESS.md](../enterprise-architecture/08-DESIGN-REVIEWS-AND-READINESS.md) | Architecture, contract, risk, policy or integration requirements | `faa69acdd910` |
| [enterprise-architecture/09-REQUIREMENTS-TRACEABILITY-MATRIX.md](../enterprise-architecture/09-REQUIREMENTS-TRACEABILITY-MATRIX.md) | Architecture, contract, risk, policy or integration requirements | `c3f23490c3ca` |
| [enterprise-architecture/10-API-EVENT-AND-CONTRACT-CATALOG.md](../enterprise-architecture/10-API-EVENT-AND-CONTRACT-CATALOG.md) | Architecture, contract, risk, policy or integration requirements | `4b97433186ee` |
| [enterprise-architecture/11-DATA-ARCHITECTURE-AND-GOVERNANCE.md](../enterprise-architecture/11-DATA-ARCHITECTURE-AND-GOVERNANCE.md) | Architecture, contract, risk, policy or integration requirements | `92b0d74cb1f7` |
| [enterprise-architecture/12-THREAT-MODEL-AND-RISK-REGISTER.md](../enterprise-architecture/12-THREAT-MODEL-AND-RISK-REGISTER.md) | Architecture, contract, risk, policy or integration requirements | `48a5d4f0c69f` |
| [enterprise-architecture/13-AI-EVALUATION-AND-MODEL-GOVERNANCE-PLAN.md](../enterprise-architecture/13-AI-EVALUATION-AND-MODEL-GOVERNANCE-PLAN.md) | Architecture, contract, risk, policy or integration requirements | `e49f536bcf83` |
| [enterprise-architecture/14-GOVERNANCE-OPERATING-MODEL-RACI.md](../enterprise-architecture/14-GOVERNANCE-OPERATING-MODEL-RACI.md) | Architecture, contract, risk, policy or integration requirements | `89d5380bc130` |
| [enterprise-architecture/15-PORTFOLIO-CASE-STUDY-AND-EVIDENCE.md](../enterprise-architecture/15-PORTFOLIO-CASE-STUDY-AND-EVIDENCE.md) | Architecture, contract, risk, policy or integration requirements | `e1f7a33bf985` |
| [enterprise-architecture/16-MASTER-ENTERPRISE-SOLUTION-ARCHITECTURE.md](../enterprise-architecture/16-MASTER-ENTERPRISE-SOLUTION-ARCHITECTURE.md) | Architecture, contract, risk, policy or integration requirements | `bb7fb333e856` |
| [enterprise-architecture/17-ARCHITECTURE-GAP-AUDIT-AND-REVIEW-REGISTER.md](../enterprise-architecture/17-ARCHITECTURE-GAP-AUDIT-AND-REVIEW-REGISTER.md) | Architecture, contract, risk, policy or integration requirements | `0b392780e42e` |
| [enterprise-architecture/18-ROLE-COMPETENCY-AND-INTERVIEW-EVIDENCE-MAP.md](../enterprise-architecture/18-ROLE-COMPETENCY-AND-INTERVIEW-EVIDENCE-MAP.md) | Architecture, contract, risk, policy or integration requirements | `033c35a1df8b` |
| [enterprise-architecture/19-ARCHITECTURE-TO-CODE-CONFORMANCE-REVIEW.md](../enterprise-architecture/19-ARCHITECTURE-TO-CODE-CONFORMANCE-REVIEW.md) | Architecture, contract, risk, policy or integration requirements | `91a2a5649848` |
| [enterprise-architecture/20-TELEMETRY-CONTRACT-MIGRATION-AND-TEST-PLAN.md](../enterprise-architecture/20-TELEMETRY-CONTRACT-MIGRATION-AND-TEST-PLAN.md) | Architecture, contract, risk, policy or integration requirements | `14d61e4a09f2` |
| [enterprise-architecture/21-IMPLEMENTATION-READINESS-ARCHITECTURE-REVIEW.md](../enterprise-architecture/21-IMPLEMENTATION-READINESS-ARCHITECTURE-REVIEW.md) | Architecture, contract, risk, policy or integration requirements | `2cd4907581c4` |
| [enterprise-architecture/22-INTERFACE-CONTROL-DOCUMENT.md](../enterprise-architecture/22-INTERFACE-CONTROL-DOCUMENT.md) | Architecture, contract, risk, policy or integration requirements | `c0e3e7636636` |
| [enterprise-architecture/24-ENTERPRISE-SECURITY-AND-ZERO-TRUST-VERIFICATION.md](../enterprise-architecture/24-ENTERPRISE-SECURITY-AND-ZERO-TRUST-VERIFICATION.md) | Architecture, contract, risk, policy or integration requirements | `ec77b7e95227` |
| [enterprise-architecture/25-EXECUTABLE-ZERO-TRUST-POLICY-AND-TESTS.md](../enterprise-architecture/25-EXECUTABLE-ZERO-TRUST-POLICY-AND-TESTS.md) | Architecture, contract, risk, policy or integration requirements | `21e8c6ed3abf` |
| [enterprise-architecture/26-ENTERPRISE-SECURITY-INTEGRATION-ARCHITECTURE.md](../enterprise-architecture/26-ENTERPRISE-SECURITY-INTEGRATION-ARCHITECTURE.md) | Architecture, contract, risk, policy or integration requirements | `611516543dc6` |
| [enterprise-architecture/27-SANDBOX-SECURITY-INTEGRATION-TEST-HARNESS.md](../enterprise-architecture/27-SANDBOX-SECURITY-INTEGRATION-TEST-HARNESS.md) | Architecture, contract, risk, policy or integration requirements | `65516e949fc3` |
| [enterprise-architecture/28-LOCAL-MQTT-AND-FASTAPI-SECURITY-SANDBOX.md](../enterprise-architecture/28-LOCAL-MQTT-AND-FASTAPI-SECURITY-SANDBOX.md) | Architecture, contract, risk, policy or integration requirements | `53ad37958aaf` |
| [enterprise-architecture/29-MQTT-TO-FASTAPI-GATEWAY-INTEGRATION.md](../enterprise-architecture/29-MQTT-TO-FASTAPI-GATEWAY-INTEGRATION.md) | Architecture, contract, risk, policy or integration requirements | `49d3040f6703` |
| [enterprise-architecture/30-INDEPENDENT-HTTP-API-AND-DURABLE-TELEMETRY.md](../enterprise-architecture/30-INDEPENDENT-HTTP-API-AND-DURABLE-TELEMETRY.md) | Architecture, contract, risk, policy or integration requirements | `518b95d43e3b` |
| [enterprise-architecture/31-REAL-MQTT-TO-DURABLE-HTTP-INTEGRATION.md](../enterprise-architecture/31-REAL-MQTT-TO-DURABLE-HTTP-INTEGRATION.md) | Architecture, contract, risk, policy or integration requirements | `e99d1b57f71e` |
| [enterprise-architecture/README.md](../enterprise-architecture/README.md) | Architecture, contract, risk, policy or integration requirements | `51a71b5d77e4` |
| [HARDWARE_30_PRODUCT_REGISTER.md](../HARDWARE_30_PRODUCT_REGISTER.md) | BOM, procurement uncertainty, power/sensor integration and acceptance | `c11c10f86e26` |
| [HARDWARE_BUYING_INTEGRATION_AND_CAREER_GUIDE.md](../HARDWARE_BUYING_INTEGRATION_AND_CAREER_GUIDE.md) | BOM, procurement uncertainty, power/sensor integration and acceptance | `3fe5041b1b07` |
| [HARDWARE_REQUIREMENTS.md](../HARDWARE_REQUIREMENTS.md) | BOM, procurement uncertainty, power/sensor integration and acceptance | `85340b9b98da` |
| [INDUSTRIAL_EDGE_AI_30_HARDWARE_END_TO_END_REPORT.md](../INDUSTRIAL_EDGE_AI_30_HARDWARE_END_TO_END_REPORT.md) | BOM, procurement uncertainty, power/sensor integration and acceptance | `d19fc9582bff` |
| [phase-01-hardware/docs/WIRING_AND_SAFETY.md](../phase-01-hardware/docs/WIRING_AND_SAFETY.md) | Actual source/bring-up scope and physical signal constraints | `af0357217628` |
| [phase-01-hardware/README.md](../phase-01-hardware/README.md) | Actual source/bring-up scope and physical signal constraints | `809621dd8199` |
| [PHASE_01_HARDWARE_IMPLEMENTATION.md](../PHASE_01_HARDWARE_IMPLEMENTATION.md) | Implementation requirements, dependencies, tests and evidence boundaries | `d9915f898d49` |
| [PHASE_02_EMBEDDED_IOT_MQTT_IMPLEMENTATION.md](../PHASE_02_EMBEDDED_IOT_MQTT_IMPLEMENTATION.md) | Implementation requirements, dependencies, tests and evidence boundaries | `a84dc9e8bf1e` |
| [PHASE_03_EDGE_AI_ONNX_IMPLEMENTATION.md](../PHASE_03_EDGE_AI_ONNX_IMPLEMENTATION.md) | Implementation requirements, dependencies, tests and evidence boundaries | `48996477cf03` |
| [PHASE_04_INDUSTRIAL_PREDICTIVE_MAINTENANCE_IMPLEMENTATION.md](../PHASE_04_INDUSTRIAL_PREDICTIVE_MAINTENANCE_IMPLEMENTATION.md) | Implementation requirements, dependencies, tests and evidence boundaries | `7e8160e6251a` |
| [PHASE_05_PRODUCTION_BACKEND_TIMESERIES_DASHBOARD.md](../PHASE_05_PRODUCTION_BACKEND_TIMESERIES_DASHBOARD.md) | Implementation requirements, dependencies, tests and evidence boundaries | `efe22c5a214f` |
| [PHASE_06_AGENTIC_AI_RAG_CONTROLLED_AUTOMATION.md](../PHASE_06_AGENTIC_AI_RAG_CONTROLLED_AUTOMATION.md) | Implementation requirements, dependencies, tests and evidence boundaries | `d476574f489d` |
| [PHASE_07_DIGITAL_TWIN_FLEET_ANALYTICS_EVALUATION.md](../PHASE_07_DIGITAL_TWIN_FLEET_ANALYTICS_EVALUATION.md) | Implementation requirements, dependencies, tests and evidence boundaries | `89af83bda400` |
| [PHASE_08_SECURITY_MLOPS_DEPLOYMENT_PORTFOLIO.md](../PHASE_08_SECURITY_MLOPS_DEPLOYMENT_PORTFOLIO.md) | Implementation requirements, dependencies, tests and evidence boundaries | `de216f3f8909` |
| [README.md](../README.md) | Product scope, source map and proposed end-to-end architecture | `5ea840181752` |

## 5. Historical references and remaining engineering inputs

The legacy reference guide covers sign-in, executive overview, equipment/assets, telemetry, hardware/devices, edge models, incidents, work orders, copilot/RAG, digital twin, backend/data, audit, MLOps/deployment, project phases and settings. It establishes intended navigation, not the behavior of a live production service. Current UI evidence is recorded separately in the dashboard review.

Before release, obtain exact delivered component labels/datasheets, an engineered circuit/sensor-mount design, independent safety/security review, approved identity/site/retention/hosting policy, real recording/label evidence, operational owners and measured targets. These gaps are made explicit in chapter 04. No existing account, broker, physical device, production service or other project was changed by this design review.

## 8. Subsequent UI reconciliation

The current product extension resolves REC-01 in the API with 30 named planned BOM categories and REC-19 in the interface with 17 workspace views/subviews. Seven superseded HTML references have moved from active assets to `archive/ui-prototypes/`; they remain design history. See `dashboard/PRODUCT_WORKSPACE.md` for precise functionality and outstanding integrations. The original review manifest is a dated snapshot and has not been rewritten to disguise these later changes.
