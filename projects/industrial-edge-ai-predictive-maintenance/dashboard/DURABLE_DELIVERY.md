# Durable synthetic delivery - 20 November 2026

This slice adds a bounded SQLite delivery spool, conflict-aware local central ingestion and explicit durable receipts. It is tested with synthetic observations only. It is not hardware enrollment, MQTT broker integration, measured ingestion, production identity, factory availability, or deployment acceptance.

## Device workspace

After creating an active synthetic test binding, use **Load synthetic delivery example**. This fills the existing observation editor with a declared synthetic boot identity; it does not verify a physical boot. **Save editor observation to queue** returns edge-committed only after the spool transaction commits. It does not claim central commitment. **Run local delivery attempt** claims one due entry and invokes the same central commit function within the local service. Its outcome and receipt are then read from durable state. **Refresh delivery state** does not attempt transmission.

The local relay is explicitly in-process, not a network test. A separate loopback HTTP worker is provided below and exercised by automated tests. Queue state survives browser reload and process exit. The existing preflight-only path still accepts ambiguous boot identity for validation, but delivery requires a declared verified synthetic boot/session to make its dedupe key unambiguous. None of these synthetic declarations establish actual device trust, calibration or freshness.

## Commit boundaries and identity

- Edge committed: the independent spool database has committed an immutable source envelope. The web process can restart without losing this entry.
- Central committed: a central observation and stable receipt have committed in the dashboard database. Retries return the original receipt, not a second observation.
- Broker receipt: unavailable. No broker acknowledgment is fabricated.

The source key is device/boot/event-type/sequence within this single local project. The canonical content hash includes binding revision and the normalized observation, excluding the per-arrival gateway receipt timestamp. Changed content under an existing key returns conflict and never overwrites the original. Site/asset/source/transport bindings remain immutable and must be active at the exact revision. Retired bindings and revoked/unauthorized accounts fail closed even when a retry refers to prior data.

This is not multi-tenant scoping or cryptographic device authentication. Browser-style local account sessions and CSRF authorize the test APIs. The central commit timestamp is generated server-side; client observation/receipt timestamps are not assumed trustworthy or used to make a stale asset healthy. Central acceptance has no incident, maintenance, model, inference or equipment effect.

## Storage, retries and failure behavior

The spool defaults to delivery-spool.sqlite3 beside the configured dashboard database. EDGEOPS_DELIVERY_SPOOL_DB can explicitly select another private path. It uses SQLite WAL, synchronous FULL transactions, a 10,000-row limit and 32 MiB of serialized envelope payloads. These are application limits, not a guaranteed physical file/disk budget; indexes, SQLite pages and WAL require additional space. Central storage is independently capped at 10,000 observations for this local slice.

Delivered entries remain retained and count toward capacity. No automatic deletion, key expiration, retention reset or hidden replay is implemented. At capacity, new observations fail explicitly with no edge acceptance. Existing identical retries remain idempotent. Capacity must be reviewed and storage provisioned before sustained operation.

Each claim holds a random lease token for 45 seconds. Expired leases can be reclaimed; a previous worker cannot complete a claim owned by a newer worker. Transient transport/5xx/408/429 outcomes schedule exponential backoff capped at 300 seconds. Eight failed attempts result in a visible blocked entry; other 4xx denials and invalid/mismatched receipts block immediately. Arbitrary exception text and credentials are never stored as last_error. Blocked entries are retained for investigation; there is no automatic requeue or source-identity rewriting.

The UI relay makes one attempt per explicit action. The HTTP worker makes one attempt per invocation. Backoff is persisted, but retries require another invocation from an operator or separately managed supervisor; no unattended process or scheduler is automatically installed. After an abrupt crash, lease expiry allows a later worker invocation to recover the entry. A lost response after central commit produces an idempotent retry with the original receipt.

Edge and central stores are separate transactions. A response can be lost after an edge/central commit; retries reconcile by key/hash. Project audit writes are not a distributed transaction with the edge file. A SQLite/disk failure cannot return a successful new commit, but it may leave a durable entry whose HTTP acknowledgment was lost. The source must retry/reconcile; do not treat an unavailable response as proof the data was never committed.

## HTTP worker

Run from the dashboard folder against an explicitly configured local test server:

```powershell
.\.venv\Scripts\python.exe delivery_worker.py --spool .local/delivery-spool.sqlite3 --server http://127.0.0.1:8877
```

Supply EDGEOPS_DELIVERY_EMAIL and EDGEOPS_DELIVERY_PASSWORD through a private local environment using a suitable test account; do not save them in source, reports, screenshots or the spool. The worker creates a short-lived authenticated session, sends a due envelope with CSRF and attempts logout afterward. It accepts only explicit loopback HTTP origins, disables environmental proxies and redirects, and has a request timeout. Failed authentication leaves the queue untouched. This is a local development worker; production requires separate scoped device/service credentials, TLS transport, secret rotation, supervision and network policy. No worker is started against the user's live installation automatically.

## API surface

| Route | Meaning |
| --- | --- |
| POST /api/acquisition/queue | Admin/operator, CSRF, current role and active binding; edge-committed after spool persistence |
| POST /api/acquisition/ingest | Admin/operator, CSRF, current role and binding; 201 new central commit, 200 identical retry, 409 conflicting content |
| POST /api/acquisition/deliver-once | Authorized local in-process test attempt; no network/hardware claim |
| GET /api/acquisition/delivery | Supported authenticated roles; bounded paged queue outcomes (default 20, limit 1-100), queue counts and central record count |

All responses retain synthetic scope, production_ready=false, hardware_connected=false, equipment_authorized=false and model_deployed=false. The separate preflight response continues to report observation_persisted=false; queue/ingest use their own explicit receipt tier instead.

## Backup and verification

The recovery tool now accepts **--delivery-spool** when that file exists. Include both the configured dashboard database and spool plus required offline reports. Restoring preserves queue states and source keys; inflight entries wait for lease expiry before another attempt. Per-store snapshots are not an atomic cross-store recovery point. Stop writers for a coordinated snapshot and reconcile pending/committed identities after a real cutover. Existing authentication/session-revocation rules still apply. See RECOVERY.md.

Tests cover restart, abrupt process exit, WAL recovery, backup/restore of an inflight entry, lost response after central commit, canonical retry hashing, conflicts, concurrent claims, stale-worker fencing, bounded capacity, read-only write failure, retry exhaustion, malformed receipts, role/retirement denial and a separate real HTTP server/worker. These are local synthetic tests, not real network outage duration, physical disk-full, power-loss hardware or industrial reliability acceptance. Next work includes supervised edge/service identity and broker integration, operational telemetry queries/freshness and qualified measured-device integration.


## Read-only saved outcome inspection

Each loaded delivery-history row now offers Inspect outcome for every supported reader, including auditors. It opens the exact loaded queue row without another service read or a delivery action. The full event key, attempt count, saved failure code and any central receipt remain separate from the browser response-load time. Pending, inflight and blocked descriptions do not invent retry times, running workers or absence from central storage after a lost response. A delivered entry shows the saved receipt tier, ID, content hash, commit timestamp and matching event key; it is not a new verification of central storage or hardware health.

Inspection requires the expected synthetic scope and false hardware/equipment/production/model flags. A delivered row requires a parseable, matching central-committed receipt with supported identities, timezone-qualified commit time and unchanged boundary flags. Inconsistent/non-delivered receipts or malformed state refuse inspection/export. This is consistency checking of a loaded status record; the API does not expose the source envelope or binding here, so the browser cannot independently recompute a content hash or infer device/asset identity. No broker receipt is created.

Export this saved outcome retains the exact status row, original receipt string, parsed receipt, reported counts/limits/retention/relay mode and distinct browser load/generation times. The service does not provide an as_of timestamp on this endpoint; the browser does not invent one. Queue counts cover all retained entries while only the selected page is returned; central count is obtained separately and is not an atomic cross-store snapshot. Payload limits do not include SQLite/index/WAL overhead. Export is read-only, synthetic, false equipment/hardware/production/model authority, with live_requery_performed=false. No observation payload, actor or credentials are included.

Refresh, a failed request and newer page loads close old inspection content and export authority. Close/Escape clears immediately and restores focus; old queued close events do not clear a reopened dialog. An unsaved observation editor remains unchanged by inspection. The change adds no route/schema, retry/requeue command, hardware product or acceptance decision. Disposable browser checks cover real pending/delivered/blocked records and saved receipts, a claimed inflight entry, lost-response-safe wording, exact export, role access, malformed/mismatched fixtures, escaped codes, loading/outage/concurrent-response clearing, new arrivals, draft retention, keyboard/focus, contrast and five widths.


## Browsing older retained queue entries

Device → Saved queue & commit receipts now has Older entries and Newest entries. Refresh and successful explicit queue/attempt actions return to the newest page. Each page contains at most 20 entries in the dashboard; global queue counts still cover every retained entry. A historical page does not become the current queue or a historical reconstruction of its states: each read shows saved states when that read ran. New arrivals do not silently replace the currently loaded page or its receipt export.

GET /api/acquisition/delivery accepts an optional opaque before cursor and a limit from 1 to 100 (default 20). The response page object contains limit, the requested before position, next_before and order=created-desc-event-asc. Ordering preserves the previous newest-created-first/event-identity-ascending tie break. Cursors encode version, creation time and event identity, are bounded and validated, and represent navigation positions rather than authorization or signed evidence. Queue counts and the selected rows share one read transaction in the spool. Central count is read separately, so this is not a cross-store atomic snapshot.

Keyset paging excludes already traversed positions when new newer entries arrive, including deterministic behavior for tied creation times. It is not a frozen multi-page snapshot: independently added older-position entries and state changes may appear in later reads. No automatic deletion or retention change is introduced. A new delivery_history index supports the traversal without altering existing rows. Receipt export includes the exact reported history page metadata and original browser load time; page context does not create a server snapshot timestamp.

Paging and refresh immediately clear old rows, close old receipt inspection/export content and disable stale page controls until a request succeeds. Outage clears old results; Refresh retries from the newest page. Late responses cannot overwrite a newer request. Observation editor drafts stay intact. Auditors retain the same read access and receive no write controls. Backend checks cover ties/new arrivals, mutable outcomes and global counts, empty/terminal/reopened pages, malformed/bounded cursors/limits, supported reader roles and denial without authentication. Browser checks cover browsing beyond 20, exact older-row inspection/export, new arrivals, draft preservation, outage/retry/loading/stale-response clearing, keyboard, contrast and five widths. No worker, retry, command, new hardware product or acceptance decision is added.


## Queue-state filtering and total-card shortcuts

Use Queue-state filter or a count card to view pending, inflight, delivered or blocked entries across the retained queue. All states is the default. Changing or clearing the filter starts at the newest matching page, clears old rows/cursors and closes old receipt/export content. Newest/Older, refresh and explicit queue/delivery actions retain the selected filter. Count cards always show totals for all retained entries, with the active filter marked; filtering is a read, not an attempt, requeue or recovery decision. Empty matches are explicit, and Clear filter returns to all states.

The existing GET endpoint now accepts optional state=pending|inflight|delivered|blocked, with empty/omitted state meaning all states. page.state records the filter and is retained in outcome JSON exports. The existing limit bounds and authenticated project-wide reader roles remain unchanged. Filtered cursors bind the traversal position to that state and reject reuse under another state or all states with 422. Existing version-1 all-state cursors remain supported only for all-state reads; filtered cursors use version 2. Cursor context is not signed authority. A new delivery_state_history index supports state/creation/event ordering while retaining the previous all-state index and existing rows.

Counts and matching rows share the same spool read transaction. State membership may change between separate page reads; this is not a frozen historical reconstruction, and filtering makes no completion, health or physical acceptance claim. Late results from a previous filter cannot replace a newer request. Unsupported returned filter context is refused, rather than labelled as a matching result. Outage clears old results/cursors and retains the selected filter for explicit retry. Observation editor text is unaffected. Auditors can filter/read/export without gaining write controls.

Additional backend and browser checks cover all states and empty matches, global counts, filtered pagination across tied positions/new arrivals, changed state membership, cursor/filter mismatch and invalid-state denial, all reader roles, exact filtered receipt export, count-card keyboard shortcuts/selection, Clear filter, filter retention on paging and refresh, changed-filter races, outage/retry, retained drafts, contrast and five widths. No worker, retry command, hardware product or readiness acceptance is added.


## Retained queue capacity visibility

Device operations now shows retained-row usage and serialized-payload-byte usage against the reporting service's spool limits. GET delivery status includes usage.records and usage.payload_bytes. Counts, usage and page rows share the same spool read transaction; the capacity totals always cover every state/page, including retained delivered entries, regardless of the selected filter. Bytes are SQLite length(CAST(payload AS BLOB)), matching the stored UTF-8 envelope budget used by enqueue. This adds no table, record mutation, limit change or retention cleanup.

The cards retain exact usage/limits, show remaining allowance, and explicitly show usage above a current limit rather than inventing free allowance. Accessible meter graphics cap their fill at the limit but retain the full actual amounts in text and aria-valuetext. Both budgets must fit a new envelope, and headroom cannot predict the size or acceptance of a future observation or reconcile concurrent writers. Idempotent existing retries retain their existing server behavior even at capacity. Limits belong to the reporting service instance; they are not historical settings, accepted equipment targets or measurements of free disk. Serialized payload bytes exclude SQLite pages/indexes/WAL and other files. No high-availability or industrial performance claim follows from a low usage value.

Export capacity summary retains the loaded usage, limits, global counts, page/filter context, retention/relay labels and browser load time, with separate browser generation time and signed calculated headroom (limit minus usage). It includes no queue payload, event identity, actor or credentials, and retains read-only/synthetic and false hardware/equipment/production/model/live-requery authority. Receipt exports additionally retain reported_usage with their existing exact row/receipt context. Opening or exporting capacity does not query a device, run delivery, delete/requeue entries or change limits.

Refreshing, filtering, paging or an outage clears old capacity cards and disables export until a supported response is loaded. Unsupported/non-integer/negative usage, nonpositive limits and a retained-entry-count mismatch refuse display/export; above-limit positive usage remains displayable. New arrivals do not rewrite an already loaded report. Observation drafts remain intact; auditors retain read/export access only. Backend and disposable Chromium checks cover empty/retained/delivered usage, stored byte accounting, idempotent/rejected enqueue, exact and reduced limits, global usage across filters/pages, report exports, invalid metadata, full/above-limit accessible rendering, stale/outage clearing, roles, contrast and five widths. Hardware, disk provisioning and physical acceptance remain pending.


## Saved queue timing and retry visibility

Delivery history now includes queued_at_utc (edge spool creation), updated_at_utc (last saved queue-row update), retry_not_before_utc for pending entries, and lease_expires_at_utc for inflight entries. The other state-specific deadline is null, and delivered/blocked entries report both deadlines null. Historical next_at values retained internally for non-pending states are not misrepresented as scheduled retries. The full queue timing appears in Inspect outcome and its exact row export; the table shows the applicable saved deadline or No scheduled retry.

These values are serialized from saved service-host Unix times into UTC at microsecond precision. Stored floating-point values and keyset ordering are unchanged. Queue creation/update are not declared device observation times, gateway receipt times or central commit timestamps. A deadline is not a live due-state check, worker-liveness proof or a promise of successful delivery. Past deadlines do not establish that the loaded entry is still pending/inflight; explicit attempts still recheck current roles, bindings, due state and lease ownership. No countdown, polling worker, retry or requeue action is added. Browser load time remains separate; this endpoint still does not claim a cross-store snapshot time.

Required selected-row timing must be finite, nonnegative and representable in UTC, with a supported saved state and the appropriate required deadline. Unsupported stored timing returns a safe 503 with no partial page; invalid client cursors/limits still return 422. Unselected rows are not presented as independently verified. No lease token, payload, actor or credentials are exposed. The browser also refuses unsupported/mismatched timing instead of displaying or exporting a partial outcome. Loading, refresh/filter/page changes and failures clear old timing/export authority, while observation drafts remain intact.

Backend tests cover known UTC conversion, transient-backoff and lease deadlines, delivered/blocked null scheduling, source timestamp separation, corrupt timing without record mutation, safe API failure and supported readers. A disposable browser suite covers pending/inflight/delivered/blocked display and exact export, no automatic attempts, preserved loaded times after changes, older/filter contexts, unsupported timing and outage clearing, draft retention, auditor access, keyboard, contrast and five widths. Hardware timing, clock verification and industrial acceptance remain pending.
