> **Historical first UI refresh.** The current 17-view implementation, profile journeys, canonical BOM, archive cleanup and verification are described in [PRODUCT_WORKSPACE.md](PRODUCT_WORKSPACE.md). Earlier counts and inventory descriptions below refer to the prior snapshot.

# EDGEOPS dashboard UI/UX review and implementation

Reviewed: 19 November 2026. This update improves the existing authenticated dashboard; it does not certify a production industrial deployment.

## Project context reviewed

- GitHub profile: https://github.com/zenithdevelopers7-source
- Repository: https://github.com/zenithdevelopers7-source/AI-Edge-Semiconductor-Career-Projects.
- Remote dashboard branch at review: `dashboard-live-edit`, commit `25f943a5a34aa1f70c9fcf8c7c595b2d265db140`.
- Repository and flagship READMEs; Phase 05 backend/time-series/dashboard blueprint; enterprise architecture index, implementation-readiness and security review documents; EA-31 MQTT-to-HTTP integration code and its recorded 12-test evidence; dashboard HTML, interactions, authentication, local storage, offline experiment registries and tests.
- Local saved-comparison/report-review extension from the preceding development milestone. This extension was installed locally and had not been pushed to GitHub at the start of this UI work.

The architecture intends ESP32 sensors → MQTT → Raspberry Pi/ONNX → FastAPI/time-series storage → investigation → reviewed maintenance. The existing dashboard is a smaller working local FastAPI/SQLite application. Authentication, session metadata, planning inventory, audit history and saved synthetic experiment verification use real local endpoints. Equipment assets, charts, alerts and maintenance examples are fixtures. The separate enterprise MQTT/HTTP lab is not the dashboard's equipment feed. Some earlier project overview documents describe older implementation states; tested source and scoped evidence take precedence over broad completion language.

## Changes implemented

| UX problem | Result |
| --- | --- |
| Dense neon styling and small competing panels | Slate surfaces, restrained teal accents, consistent spacing, clear headings and status semantics across all 12 sections |
| Flat navigation mixes unrelated tasks | Operations, Intelligence and Workspace navigation groups with consistent outline icons |
| Decorative uptime/failure-risk values resemble measured outcomes | Overview prioritizes fixture fleet counts, demo alerts, zero connected devices and offline deployment state |
| Multiple inconsistent sensor values and vibration units | Overview readings use the telemetry fixture source; vibration remains acceleration in m/s², with no unsupported conversion to mm/s |
| Repeated headings obscure the page hierarchy | One visible page heading with a concise per-page source/scope indicator |
| Asset rows lack investigation context | Keyboard-operable asset detail dialog, unavailable measurement state, clear provenance and routes to signal examples and alerts |
| Search only sends the user to a section | Ctrl/Command+K workspace search, page/asset/alert results, keyboard navigation, clear empty states and mobile access |
| Asset filtering is difficult to reset or organize | Combined search/status filters, name/area sorting, and a single clear-filters action |
| Charts are difficult to inspect or reuse | Expandable signal table and selected-signal CSV export, consistently labeled synthetic |
| Fixed table density | Comfortable/compact browser preference with storage-unavailable fallback |
| Sign-in is visually disconnected | Matching workspace identity, local illustration assets, clearer account limitations and familiar form hierarchy |
| External font and unavailable photo URLs add fragile requests | Local system fonts and existing local SVG illustrations |
| Audit access failures incorrectly clear experiment reports | Independent experiment and audit error handling |

Dialog focus is contained by native modal dialogs; Escape explicitly closes dialogs even when search input has text, and invoking controls regain focus. Reduced-motion preferences are respected. Table scrolling is contained within the panel. The user-visible API check time describes service verification, not equipment measurement freshness. All existing report approval authorization and CSRF controls remain enforced by the server.

## Verification

- 54 non-browser automated tests passed. The 24 existing Python Playwright tests are skipped in the current local Python environment because that package is not installed; they remain in CI.
- Real Chromium saved-comparison review acceptance passed: authenticated save/review, durable notes/history, escaping, outage recovery and auditor read-only behavior.
- New real Chromium workspace acceptance passed: search and keyboard behavior; modal focus restoration; asset filters/reset/sort; telemetry table and CSV; preference persistence; and all 12 sections at 1440, 1024, 768, 390 and 320 pixels without document overflow.
- Desktop, sign-in and mobile screenshots rendered and inspected. These are local prototype checks, not a full accessibility audit, security assessment or load test.
- The browser CI workflow now includes the workspace acceptance test. A local pass is not a claim that GitHub Actions has run this change.

## Next production implementation gates

1. Authoritative asset/device registry, canonical telemetry units and quality/provenance fields, bounded history APIs and stale-data handling.
2. Persistent incident and work-order services, state transitions, assignment, scoped authorization and independent human approval.
3. Enterprise identity, reviewed role/asset/site authorization, explicit database migrations and controlled account administration.
4. Production data storage and ingestion reliability, observability, retention, backup/restore and rollback verification.
5. Curated labeled equipment datasets, leakage review, calibrated evaluation and controlled model releases.
6. Physical hardware integration and independent engineering, security and safety validation.

This UI milestone does not implement the proposed Next.js/PostgreSQL/TimescaleDB migration, production OIDC, real-time industrial telemetry, hardware control, model deployment or a live AI copilot. Those require backend and integration work with separate evidence.
