# Acquisition contract and synthetic identity foundation

This is the first contract/registry slice toward the production design's B2 foundation. It is a local, project-wide synthetic test service, not physical enrollment, tenant/site authorization, measured ingestion, a broker, a spool, or an operational asset registry. Existing synthetic ledger units and the original EA-22 V2 schema are unchanged.

## Device workspace

Device > Test bindings & observation preflight provides persistent simulated device/site/asset bindings. Administrators create and retire test bindings; operators can read and run preflight; auditors can read. Profiles do not grant these roles. The form requires explicit identifiers, simulator reference and a configuration SHA-256 supplied by the operator. It never silently creates bindings, issues credentials, claims calibration, or enables equipment.

The synthetic example is loaded only on request into the editor. It uses the chosen active test binding, unavailable boot identity, receipt-only clock and null readings for all disconnected sensors. It is not a hardware recording. Validate only checks the input; it does not save an observation, issue a commit receipt, run inference, or trigger an incident/work order. Retiring a binding prevents further successful preflight. Existing physical-device readiness guidance and planned hardware views remain available.

## Interfaces

| Interface | Behavior |
| --- | --- |
| GET /api/acquisition-bindings | Authenticated project-wide test list, 1-100 bounded page size, explicit next cursor |
| POST /api/acquisition-bindings | Admin + CSRF + current session/role inside transaction; 201 after commit, identical active retry 200, conflicting/retired identity 409 |
| POST /api/acquisition-bindings/{device_id}/retire | Admin + CSRF + current role + exact revision; append history, prohibit identity reuse |
| GET /api/acquisition-contract | Pydantic-generated JSON Schema for the local synthetic profile; includes version/profile boundary |
| POST /api/acquisition/validate | Admin/operator + CSRF, active exact site/asset/device mapping; validate only, no observation persistence |

Bindings are immutable site/asset/source/transport mappings, with simulator/configuration references, creator, timestamps and revisioned retirement history. They are not aliases for the 12 browser fixture assets or for legacy firmware IDs. Binding changes require a new test identity. Mutations and their audit/history commit together. Existing accounts/report/planning/readiness tables are retained; two new tables begin empty.

## Contract profile

`edgeops-local-synthetic-v2-preflight-v1` is a stricter synthetic-only profile using the existing `telemetry.sample` / `2.0` field vocabulary. It is not a replacement for the original candidate, which also describes future measured/replayed sources. The generated JSON Schema specifies structure; the server additionally enforces semantic quality, clock and boot rules through validators.

- Unknown fields are forbidden at every nested level; source must be synthetic and transport must be simulator.
- Identifiers are bounded ASCII letters/digits/underscore/hyphen; sequence and uptime are strict unsigned 32-bit integers. Booleans and numeric strings do not become numbers.
- Acceleration fields retain m/s2, current retains A, voltage V and case temperature C. No velocity field, mA conversion or new firmware metadata is silently inserted.
- Readings must be finite numbers or null, bounded to a broad parser profile of +/-1e12. These are message limits, not accepted physical sensor ranges or hardware ratings.
- Valid channels require numbers; legitimate zero is preserved. Invalid/disconnected/stale sensor groups require null values. Partially available samples remain inspectable as input without implying model eligibility.
- Timestamps must be explicit strings with timezones. A declared verified device clock needs a device time. Verified session needs a boot ID; unavailable session must not invent one. These declarations are checked for consistency, not externally verified.
- An active exact binding is checked under a transaction. Changing site/asset or using an unknown/retired identity is denied. This remains project-wide local authorization, not multi-tenant isolation or cryptographic device identity.
- Validation errors return safe locations/types/messages without echoing raw input, credentials or non-JSON NaN values.

All responses retain production_ready=false, hardware_connected=false, equipment_authorized=false, observation_persisted=false and device_credential_issued=false. No readiness criterion is automatically accepted.

## Verification and next slice

Seven new test cases cover schema/quality/time/boot semantics, finite and strict types, concurrent idempotent creation, binding conflicts, persistence, retirement, CSRF/roles/current-role rechecks, mismatched scope and pagination. Chromium exercises creation/reload, synthetic example validation, measured-source denial and retirement before the existing 18-workspace responsive/contrast checks.

The following local synthetic delivery slice is now implemented; see DURABLE_DELIVERY.md for the bounded spool, conflict-aware central ingestion, receipts and remaining deployment limits. A preflight success must never be presented as central commitment. Real enrollment requires separately designed credentials, scoped identity, physical mapping, accepted contracts and commissioning evidence when hardware arrives.


## Explicit example targeting and editor protection

Device setup now requires an explicit active test binding from the currently loaded registry page before either example button is enabled. It never selects the first active row automatically. The picker shows device/site/asset and a separate context shows the selected revision, simulator reference and full configuration digest when loaded. Picking a device changes no editor text and creates no record. Paging, refresh and list failure clear the selected target; the existing editor text remains. Retired bindings cannot be selected. Administrators and operators can prepare examples under existing server permissions; auditors have no preparation controls.

Load synthetic example prepares the existing preflight-only profile, with null boot identity and unavailable session declaration. Load synthetic delivery example prepares the same chosen binding, with a newly declared synthetic boot identity and verified session field as required by the existing delivery contract. Both use null disconnected readings, unchanged SI measurement keys and the same original hardware scope. Preparing an example does not validate, queue, deliver, enroll equipment or verify physical sessions. These remain separate explicit actions.

If the editor contains text, including invalid JSON, a dialog defaults to Keep editor text. Keep or Escape preserves the exact text and returns focus; only Replace editor text discards it. The dialog identifies the proposed target and example type. Confirmation rechecks the current loaded page, selection, active binding reference and original editor text before replacement. Refresh, target change or editor input cancels pending replacement; a queued close event cannot cancel a newly opened dialog. Repeated loading requires a new explicit replacement decision.

Validation results belong to the editor version that was submitted. Editing, replacing or refreshing invalidates pending results so an older response cannot label new text as passed. No new endpoint, database table, credential, acceptance record or hardware product is added. The browser acceptance suite covers multiple active and retired identities across pages, exact target context, all-null examples and boot profiles, preserved invalid drafts, Keep/Escape/Replace and focus, stale confirmation and validation races, outage/retry, roles, escaped references, five widths and contrast. Installed project records remain unchanged by this UI-only preparation change.
