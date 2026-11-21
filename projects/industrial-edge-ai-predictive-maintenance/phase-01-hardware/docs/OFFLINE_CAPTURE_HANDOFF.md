# Offline capture handoff — awaiting hardware arrival

Status: hardware ordered, not yet received, as reported by the owner. The existing 30-product selection and physical connection pack are unchanged. No device has been connected, enrolled, calibrated or accepted by this work.

## What is prepared

`scripts/prepare_capture.py` converts an existing V1 USB serial capture CSV into an offline candidate V2 evidence folder. It opens no serial port, makes no network requests, sends no equipment commands and writes no dashboard database. Python 3.12 or later is sufficient; runtime dependencies use the standard library.

The authenticated dashboard continues to accept synthetic observations only. These candidate records are not an ingestion feature or a production release. Measured or replayed records stay offline. Do not relabel them as synthetic to bypass the dashboard boundary.

## Available now: synthetic demonstration

Run from `phase-01-hardware` in PowerShell. Choose an output directory that does not already exist:

```powershell
python scripts/prepare_capture.py prepare --input examples/offline-capture/synthetic.capture.csv --attachment examples/offline-capture/synthetic.attachment.json --output evidence/synthetic-handoff-001
python scripts/prepare_capture.py verify evidence/synthetic-handoff-001
```

The example contains no readings from physical equipment. The attachment says `NOT-CONNECTED`. Neither command connects hardware. A successful preparation reports two accepted rows and zero quarantined rows, with physical verification and ingestion readiness false.

## When the ordered hardware arrives

1. Follow the existing physical connection pack for the same 30 selected products. Resolve the exact ordered board labels, motor/driver current limits, INA219 shunt and supply ratings before energizing. This software handoff grants no electrical approval.
2. Perform the pack's staged sensor-only checks first. Existing firmware reports V1 over USB serial at 115200 baud, nominally once per second. No motor actuation is implemented by this adapter.
3. Capture with the existing `scripts/capture_serial.py` instructions. Always use a new capture filename: the capture command now refuses existing files before opening a serial port. Preserve the original capture and record the actual connection configuration separately. Review the capture exit status and summary before conversion.
4. Copy the example attachment to a new file. Fill in site, asset and device identifiers, actual port, exact board reference and configuration reference. Keep `v1_device_id` equal to the firmware's actual identity (currently `motor-001`). Set `source_type` truthfully to `measured` for direct physical capture or `replayed` for replay. Keep `physical_verification: unverified`, `calibration: not_verified`, `transport: usb-serial` and `profile: edgeops.serial-attachment.v1`. These classifications are operator declarations, not hardware authentication.
5. Run `prepare` with that capture and attachment, using a new output directory. Run `verify` on the resulting folder, then review every quarantined row and all provenance before any later integration.

Identifiers allow ASCII letters, numbers, hyphen and underscore, maximum 64 characters. Attachment keys must match the example exactly. Do not store passwords, certificates or secrets in the attachment. Board/configuration references are descriptive references, not independently verified credentials.

## Transformation and review rules

| V1 capture | Candidate V2 output |
| --- | --- |
| ADXL345 acceleration in m/s² | Same units and values for valid sensor; all three axes null when invalid |
| DS18B20 temperature in °C | Same value when valid; null when invalid |
| INA219 bus voltage in V | Same value when valid; null when invalid |
| INA219 current in mA | Divided by 1000 once to A when valid; null when invalid |
| Valid numeric zero | Preserved as zero |
| Captured gateway UTC | Preserved as the receipt instant, normalized to UTC; conversion time is separate |
| No verified device UTC or boot UUID in V1 | Device time and boot ID null; gateway-receipt-only clock; unavailable session |

Headers must be the exact 14-field V1 capture set, with no duplicates. Booleans use the capture writer's `True`/`False` text. Counters must be unsigned 32-bit integers and numbers finite. Missing or extra values, unknown device identity and inconsistent aggregate validity are quarantined. An invalid sensor flag does not establish whether the fault was disconnection, calibration or another cause.

Sequence nonincrease, uptime decrease (including rollover), or receipt-clock regression quarantines that record and every later record. This is an unresolved boundary requiring review, not proof of a restart. A sequence gap is counted only between accepted records; it is not independently established packet loss. No verified sessions are inferred, even for monotonic captures. Limits: 16 MiB input and 10,000 rows per preparation; split large captures deliberately before conversion and retain originals.

## Evidence folder and exit codes

The new folder contains the original `source.capture.csv`, canonical `attachment.json`, accepted `observations.jsonl`, rejected-line reasons in `quarantine.jsonl`, and `manifest.json` with counts, file sizes and SHA-256 hashes. The verifier checks inventory, hashes, counts, provenance flags, and recomputes the transformation from the included original. Existing output folders are refused. Preserve evidence with appropriate access controls; captures contain operational identifiers.

Hashes detect corruption and inconsistent edits. They are not signatures, trusted timestamps, source authentication or proof against a party rewriting the entire folder. Capture UTC is a gateway declaration, not independently verified time. `hardware_connected`, `physical_source_verified`, `calibration_verified`, `ready_for_ingestion` and `production_ready` remain false. Historical evidence cannot establish current hardware connection.

`prepare`: exit 0 means preparation completed with accepted rows and no quarantine; exit 2 means the folder was written but requires review (quarantine or no accepted rows); exit 1 means preparation failed. `verify`: exit 0 means local package consistency only, even when `requires_review` is true; exit 1 means failure. Always inspect the printed review flag. Successful conversion never establishes physical or production acceptance.

## Software verification

Test dependencies are separate from runtime dependencies:

```powershell
python -m pip install -r tests/requirements.txt
python -m unittest discover -s tests -v
```

The 28 software checks use synthetic fixtures and simulated serial streams only. They cover the V1 parser, interrupted and oversized messages, output preservation, disconnection, and capture-to-adapter compatibility, and compile-record inventory boundaries. Adapter output is checked against the existing candidate V2 JSON Schema and semantic rules. Physical wiring, acquisition accuracy, calibration, electrical safety, long-duration reliability, deployment and industrial acceptance remain pending.

### Capture behavior and result interpretation

The USB capture reader buffers timeout fragments until newline, limits a complete line to 4096 bytes including its terminator, drains oversized lines before accepting the next record, and rejects malformed UTF-8, duplicate JSON fields, extra fields and out-of-range V1 counters. A trailing incomplete record is counted as invalid and is not written. Complete rows are flushed to the CSV as they are captured; flushing is not a guarantee against power loss. No automatic reconnect or resumption is performed.

The JSON summary reports `records` (complete valid-format records), `invalid` (rejected/incomplete frames), `sensor_invalid` (saved records with a false aggregate sensor flag), `sequence_gaps` (observed counter gaps), and `discontinuities` (nonincreasing sequence or decreasing uptime). Saved sensor-invalid readings remain explicitly flagged in V1 and become null by sensor group in V2. Neither records nor gaps establish physical accuracy or actual transport loss. Discontinuities do not establish a verified reboot; the offline adapter quarantines the unresolved boundary.

Capture exit 0 means at least one complete valid-format record was saved; review sensor flags and counts even on success. Exit 2 means no such records were captured. Exit 1 covers file or serial connection failure; exit 130 means the operator interrupted capture. Failures and interruptions may leave a partial or empty new CSV; preserve it for review and use another new filename. No raw serial payload or device error text is printed by the failure handler. This utility opens only the requested USB serial port and does not send application-level equipment commands; opening a serial port may itself reset some ESP32 boards through their USB bridge.
