# Persisted synthetic telemetry explorer - 20 November 2026

The Telemetry workspace now queries the central synthetic observation records created by the delivery service. It does not replace or relabel the historical browser fixtures or the separate mm/s synthetic research ledger. No measured source, physical device, inference, alert or work-order effect is introduced.

## Use

Open **View persisted telemetry** on a Device test-binding row, including a retired binding, or enter its exact test device ID in Telemetry > Persisted observation explorer. Only observations that received a central commit appear. A merely queued observation is absent until delivered. Empty and unknown bindings are explicit states; no data is generated automatically.

Choose one of six SI channels: acceleration X/Y/Z in m/s2, case temperature in C, bus voltage in V, or current in A. The newest value on a page is shown as recorded, even when missing; the interface does not substitute an earlier valid value. Zero remains a legitimate reading. Missing/invalid/stale-at-observation sensor groups are null according to the acquisition contract and create chart gaps, not zero points. Session changes break connecting lines.

The chart is equally spaced **central commit order**, not a source-time waveform. UTC commit labels show its endpoints. It does not establish sampling rate, vibration spectrum or source timing. The accessible table and JSON page export retain exact readings, units, quality, source timestamps, identity and receipt references. Existing fixture charts and CSV remain available below, with their existing provenance.

## Time, quality and age

Three timestamps remain distinct: declared device time, declared gateway receipt time and server-generated central commit time. A newly delivered backlog cannot become recent merely because its central receipt is recent.

- A declared verified synthetic device clock plus an observation timestamp permits an observation-age calculation.
- An unavailable/unverified clock remains **clock-unverified**; gateway/central receipt time is not substituted.
- Old observations are **stale** relative to the selected display threshold.
- A declared observation later than the server's snapshot time is **future-time**.
- **within-display-age** only means the declared synthetic timestamp is within that display threshold. It is not a healthy-device, trustworthy-clock or accepted-production claim.

The default 60-second threshold is an operator display policy, not an approved measurement, alert or availability target. It is bounded to 1-86400 seconds. Sensor quality and declared calibration are shown separately; a valid number does not prove calibrated hardware. All observations remain synthetic declarations.

Data is retrieved on explicit refresh/page navigation. Age labels advance locally every five seconds using elapsed monotonic browser time anchored to the server response; this does not fetch new observations. The loading timestamp is visible. The JSON export preserves the server snapshot and its as_of timestamp, not a falsely refreshed data set. Device/filter changes clear the old result and disable export until the new query succeeds. Outages clear the table/chart rather than displaying a stale result as current authority.

## Query contract

`GET /api/acquisition/observations?device_id=...&limit=50&max_age_seconds=60&before=...` is read-only for supported authenticated local roles. It is project-wide authorization, not multi-tenant/site policy. Device ID is required and bounded; limit is 1-100. The response includes binding status/site/asset, all six channel definitions, as_of, age policy, records, next_before and explicit synthetic/non-production boundaries.

History uses keyset pagination ordered by server commit time and event key. Tied timestamps are deterministic; newer arrivals do not shift an older-page cursor into repeated records. Older/newest page controls are explicit. The first page is not an asset-health calculation, and a historical page's newest row is not advertised as the current measurement. Unknown device IDs return 404. A retired binding's committed history remains readable.

The database index covers device/commit/key. Reads are bounded and use a transaction snapshot. Each returned envelope is checked against its typed contract, canonical content hash, source key, stored device/revision and immutable binding. Corrupt or inconsistent selected records return 503 without partial history. Hash checking is content integrity against stored metadata, not independent digital-signature verification or proof of a trustworthy database administrator. No PII actor field is returned.

## Verification and limits

Five API tests verify zero/null/SI semantics, clock ambiguity, stale backlog despite recent receipt, future timestamps, operator display thresholds, pagination with tied commits/new arrivals, bounded parameters, supported roles, retired history and corrupt-content rejection. The browser suite exercises real committed records, two numeric points including zero, missing-current gaps, source age states, JSON export, outage clearing/retry and navigation from Device. Existing fixture controls/exports and all 18 workspaces remain tested at five widths with text contrast checks.

This slice adds one history index and no seeded observations or changes to existing records. Production ingestion, real device clocks/calibration, fleet-wide query isolation, durable operational incidents, managed time-series retention and qualified performance/load/freshness targets remain separate work.

## Empty-state and selection refinement

Telemetry now offers a picker populated from the first 100 existing test bindings, with explicit refresh and manual ID entry for other pages. Selecting a device fetches its history; it never creates a record. With no selection, no committed records, unavailable history, or no numeric values for the selected channel, the interface presents a clear empty/setup message instead of an unexplained blank chart. The table and pagination stay hidden until applicable. Device setup and existing demonstration charts are directly reachable; synthetic records remain opt-in operator actions.


## Explicit incident preparation

Administrators/operators can choose Create incident for a saved observation whose immutable binding asset matches one of the existing dashboard assets. The form shows all six channels/declared sensor quality and asks for interpretation/severity. The server rechecks source contract/hash/receipt/identity and the binding under the write lock, then saves a frozen source capture with the incident. No threshold, model or reading creates cases automatically. Arbitrary test asset IDs remain valid for telemetry, but are not mapped to dashboard assets implicitly. Auditors retain read-only history access.

Incident details retain units, zero/null values, declared clock/gateway times/quality and source identity without a live freshness/health claim; export and linked planning retain that capture. Exact retries avoid duplicate cases, and one source case per creating account/observation is allowed. Failed saves preserve interpretation; filter/device changes close stale creation editors. See INCIDENT_WORKFLOW.md for API, permission, recovery and verification details. No hardware or production readiness changes.


Existing incidents can retain additional observations through Alerts → open incident → Attach saved observation. The paged chooser loads committed history without device access, requires exact asset/site context and a note, and freezes all six channels/source declarations. The original case/source remains unchanged. Exact retries, duplicate/state/capacity guards, current account scope and atomic audit/history/capture apply. Captures appear in incident history/export and frozen maintenance context; see INCIDENT_WORKFLOW.md. This does not automatically detect, correlate or resolve physical faults.


## Read-only saved observation inspector

Each committed-history row now has Inspect reading, separately from the existing explicit Create incident action. It opens a read-only dialog using that row from the currently loaded history page. No device, server or incident write is requested by opening the inspector. All supported readers, including auditors and readings for retired or unmapped test bindings, can inspect the saved context under the existing project-wide history permissions. Unmapped assets gain no inferred incident mapping.

The inspector shows all six channel values with the loaded SI definitions, preserving exact displayed numeric precision, zero, negatives and explicit missing values. Declared sensor quality stays separate from calibration, session quality and clock quality. Service snapshot time, central commit, declared device time and declared gateway receipt remain distinct. An expandable identity section retains event/content identities, central receipt, saved envelope binding revision, boot identity and uptime. Binding status is labelled when history loaded; it is not invented as status at the original observation time.

Age labels use the existing elapsed monotonic-time display policy, including clock-unverified, stale, future-time and within-display-age. They are not device-health or accepted operational targets. Opening the inspector does not refresh its source snapshot, establish verified clocks/calibration or independently recheck source integrity. New observations do not silently replace the loaded row. Changing device/age queries, refreshing or paging clears/closes old inspection content; ordinary Close/Escape restores focus to the row, with a safe fallback if that row was redrawn. Closing and reopening cannot replay a delayed close against a newer inspector.

Export this saved observation downloads one complete loaded record, all six channel definitions, parent binding/site/asset metadata and the original service as_of/display threshold, with explicit synthetic/read-only and false equipment/hardware/production/live-requery flags. Browser inspection generation time is separate from the source snapshot time. Local age-label advancement never rewrites original exported server ages. Unsupported source identity, unit definitions, scope or malformed display metadata refuses inspection/export; it does not create a partial verified record. The page-wide history export remains unchanged.

Inspection preserves any separate unsaved incident interpretation editor underneath it. It never fills, submits or automatically creates that case. Existing writer and auditor controls remain separate, and service failures clear inspection actions instead of retaining an old result as current. The inspector adds no endpoint, schema, hardware part, command or acceptance decision.

A disposable Chromium suite covers precise/zero/null/negative six-channel SI values, quality/clock/receipt identity, exact record export and original server ages, locally advancing age labels, keyboard close/focus restoration, retained incident interpretation, older pages/new arrivals, retired/unmapped/auditor reads, unsupported identity/unit/scope and outage clearing, escaped metadata, zero inspection service reads/domain writes, contrast and five widths. Unsupported metadata scenarios are isolated browser fixtures; ordinary history and age scenarios use persisted synthetic records. Physical acquisition and production acceptance remain pending.


## Read-only same-page observation comparison

Select Compare on two committed-history rows, then Compare selected readings. First selected is A; second is B. Both records must belong to the same currently loaded device/site/asset page. A third selection is disabled until one is cleared. Deselecting A makes the remaining selection A. Channel changes retain selections; refresh, device/age edits, paging, or a failed history request clear them and close old comparisons. This selection is temporary browser state and creates no saved incident or comparison registry record.

The dialog shows all six exact loaded numeric inputs, explicit missing values, declared sensor quality for each input, and calculated B minus A in each channel's SI unit. Calculated differences use browser floating-point arithmetic and display at most six significant digits; they are not exact measured differences. Missing inputs and non-finite arithmetic results remain unavailable, with a reason, rather than zero. No percentage, time-normalized rate, alarm, significance or equipment-health interpretation is calculated. Boot identity changes are labelled as cross-session; neither equal boot identity nor commit ordering establishes continuous source sampling. Source time, gateway receipt, central commit, original service snapshot, clock/calibration/session declarations, envelope revisions and immutable identities remain separate for both records.

Explicit JSON download retains both complete loaded records, channel definitions, original snapshot/age policy, selection order and unrounded browser arithmetic results with delta_state. Local monotonic age-label updates do not rewrite original exported server ages. Browser generation time is separate. Scope is local-browser-persisted-observation-comparison, with synthetic/read-only and false hardware/equipment/production/live-requery flags. Unsupported identity, scope, definitions or duplicate observations refuse comparison/export. This is a visual comparison under existing read permissions, including auditors and retired/unmapped test bindings; it does not independently re-query or re-verify the source.

Close/Escape immediately clears dialog/export contents and restores focus while retaining selections. A queued close cannot clear a newer dialog. Separate unsaved incident interpretations remain intact. The comparison adds no endpoint, schema, hardware part, equipment command or acceptance decision. Its disposable Chromium suite verifies selection/order/cap, exact zero/null/negative inputs and deltas, changing quality/session/time context, export identity and original ages, local age advancement, query/channel/paging behavior, new arrivals, retired/unmapped/auditor reads, failed/unsupported source clearing, escaped metadata, keyboard/focus, five widths, contrast and zero comparison reads/domain writes.
