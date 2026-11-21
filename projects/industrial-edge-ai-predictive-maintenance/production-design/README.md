# EDGEOPS — Complete Production System Design Baseline

**Version:** 1.0 candidate · **Date:** 19 November 2026 · **Disposition:** design for review, not deployment authorization.

This package consolidates the 48 existing project Markdown documents, their recorded lab evidence, the 30-category hardware register, and the current embedded/dashboard/integration source. It defines a single implementation direction for a monitored, recoverable, human-governed condition-monitoring platform. The planned physical scope is one guarded 12 V DC motor; additional fleet assets are simulations until separately commissioned.

## Read in this order

1. [System architecture and operating model](01-SYSTEM-ARCHITECTURE.md)
2. [All 30 hardware categories and physical integration](02-HARDWARE-INTEGRATION.md)
3. [Data contracts, identity, workflows and dashboard](03-CONTRACTS-AND-WORKFLOWS.md)
4. [Implementation backlog, requirements and release acceptance](04-IMPLEMENTATION-AND-ACCEPTANCE.md)
5. [Source review, conflicts and evidence register](05-SOURCE-REVIEW.md)
6. [System architecture diagram](system-architecture.svg)

The numbered EA-01–EA-31 documents remain historical context. This package does not consume the EA-32 identifier already suggested for durable-spool implementation in EA-31. It does not silently change the existing V1 serial format, V2 candidate schema, synthetic-only lab services, dashboard accounts or hardware state.

## Target end-to-end flow

```text
Protected motor bench + sensors
  → ESP32 acquisition and quality checks
  → private authenticated MQTT / reviewed serial-to-Pi commissioning path
  → Raspberry Pi validation, durable spool, features and approved ONNX inference
  → authenticated HTTPS ingestion with conflict-aware idempotency
  → PostgreSQL domain records + supported time-series storage + transactional outbox
  → fleet, device, telemetry, incident, maintenance, model and audit workspaces
  → cited advisory guidance → independent human work-order approval
  → technician evidence → verification → closure and recovery/audit evidence
```

All 30 hardware categories are accounted for. Some are installed components; others are commissioning instruments, conditional circuit components or replacement spares. Inclusion does not mean every item must be connected simultaneously. Purchases, delivery, exact motor/driver models, electrical ratings and physical testing remain unverified.

## What this design resolves

- A canonical 30-category BOM replaces the dashboard's grouped inventory as the design reference, without rewriting legacy identifiers.
- A staged serial-to-native-MQTT migration preserves the real capabilities and identity limitations of current firmware.
- Raw acceleration, vibration features, temperature and DC electrical observations have explicit units and quality rules.
- Broker acknowledgement, edge durability and central database commit become separate observable states.
- A modular backend owns assets, incidents, work orders, authorization and audit; the browser never owns operational truth.
- Report approval, work-order approval and model-release approval become separate workflows.
- Production web migration follows stable contracts and preserves existing dashboard behavior as acceptance evidence.
- Every stage has failure behavior, traceability, implementation dependencies and release evidence.

## Status vocabulary

**Designed:** specified here. **Implemented:** code exists. **Tested:** exact scoped execution evidence exists. **Commissioned:** exact hardware and installation passed applicable checks. **Production accepted:** authorized operators accept a defined deployment with its remaining risks. These are separate states.

The design is complete as a reviewable baseline. Exact component certification, site-specific electrical design, approved operating targets and independent production acceptance require real inputs and evidence; they are not invented to make this document appear finished.
