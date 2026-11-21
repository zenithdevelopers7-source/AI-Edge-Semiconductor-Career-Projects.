# Physical build preparation in Hardware

This view uses the same 30 selected products. No replacement board, sensor, motor, driver, supply or accessory is introduced. The source is the existing phase-01 physical connection matrix and sensor-only named-net diagram, itself based on the newer GitHub sourcing table.

## Order report and physical facts

The user confirmed all 30 selected categories were ordered. The catalog now reports `ordered_count_user_reported: 30`, dated 20 November 2026, and each lifecycle is `ordered-user-reported`. This count concerns selected product categories, not an inspected count of individual pieces or pack quantities. `purchased_count` remains unknown as independently verified evidence; `purchase_verified`, `connected` and commissioned/physical-instance claims remain false or unverified. Order reporting does not create a sensor reading or satisfy a readiness criterion.

Hardware includes the power-off layout, conditional sensor harness, Pi assembly sequence and the unresolved motor-circuit review. It shows all 30 roles, including instruments, optional installation items and the cold spare. Export downloads the fixed-scope JSON plan. The sensor diagram is a named-net reference, not a guessed physical board-pin layout or a released motor-power circuit. No progress boxes silently mark equipment safe or connected.

The firmware reference remains GPIO21 SDA, GPIO22 SCL and GPIO4 temperature data, subject to actual board and sensor pin/supply identification. Motor power and driver-control assignments remain pending the ratings explicitly absent from the source. This view does not add a software motor-control action or require new hardware. Hardware testing is deferred; this software change performs none.

## Interfaces and source consistency

`GET /api/hardware/physical-plan` and `GET /api/hardware/physical-plan/sensor-map` require a supported authenticated local role. They are read-only. The plan rejects unsupported/expanded IDs, physical-connected or production-ready claims, replacement permissions and unexpected reference pins. It includes source and diagram hashes. The diagram is served only if its content matches the plan's recorded hash. The catalog's `/api/hardware` lifecycle now distinguishes the user order declaration from verified purchase/installation.

The packaged `physical-build-plan.json` is a snapshot of the phase-01 connection matrix. Its CSV hash uses UTF-8 bytes with LF-normalized line endings; row names and order are tested against that source. The map copy is checked byte-for-byte. These are versioned source checks, not independent physical verification or signed purchase evidence. If the selected guide is revised, regenerate/review this snapshot and map together. No private order numbers, supplier accounts or payment evidence are included.

On a failed refresh, the view clears prior instructions, hides the diagram and disables export. It cannot present stale instructions as newly verified. Existing component filters, details, CSV and the other 17 workspaces remain accessible.

## Verification

Three new API/source cases verify all 30 identities, no additions/substitutions, agreement with the matrix/map, supported roles, read-only routes and the separation of ordered versus connected/verified states. The workspace browser suite exercises the map, 30-row table, export, unavailable/retry handling, all 18 views at five widths and text contrast. Existing review, delivery, readiness and telemetry checks remain in place. No bench action, hardware commissioning, database schema migration or physical acceptance occurs during this update.
