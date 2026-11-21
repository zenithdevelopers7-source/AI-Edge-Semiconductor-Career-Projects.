# Phase 01 — Runnable Sensor Acquisition Starter

This is **starter source code**, not a claim of tested hardware. The firmware supports ESP32 + ADXL345 (I2C), INA219 (I2C), and DS18B20 (GPIO4). It prints one JSON Lines record per second. A laptop capture utility saves and validates the records.

Hardware arrival is pending. The [offline capture handoff](docs/OFFLINE_CAPTURE_HANDOFF.md) prepares existing V1 capture CSV files as candidate V2 evidence without connecting devices or importing measured readings into the dashboard. The same 30-product selection remains unchanged.

Use the [compile-only build guide](docs/FIRMWARE_BUILD.md) to check the existing ESP32 firmware before hardware arrives. Build tools/platform/direct libraries are fixed to explicit versions; GitHub compiles the target without uploading it. Compilation does not establish physical compatibility or acceptance.

## Quick start
1. Read [wiring and safety](docs/WIRING_AND_SAFETY.md) before powering anything. Keep the motor disconnected during initial tests.
2. Install VS Code with PlatformIO. Open `firmware/` as a PlatformIO project.
3. Check your board and sensor breakout voltages/pinouts. Build and upload: `pio run -t upload`.
4. In a separate terminal install Python 3.11+, then `python -m pip install -r scripts/requirements.txt`.
5. Identify serial port (macOS often `/dev/cu.usbserial-*`, Windows `COM3`, Linux `/dev/ttyUSB0`).
6. Capture: `python scripts/capture_serial.py --port /dev/cu.usbserial-XXXX --seconds 600 --output data/baseline.csv` (replace port).
7. For offline software checks, install `python -m pip install -r tests/requirements.txt`, then run `python -m unittest discover -s tests -v` (Python 3.12+ for the complete adapter suite).
8. Inspect valid-record rate, sample interval, invalid sensor flags, and save a test report.

## Scope and limitations
- One **1 Hz summary** record is emitted. It is not high-rate raw vibration acquisition, bearing-fault frequency analysis, or RUL prediction.
- ADXL345 output is acceleration along 3 axes in m/s². Sensor orientation and mounting affect readings.
- INA219 uses its library's default calibration: verify actual shunt and load limits; do **not** insert it into a motor path unless the entire module is rated for startup/stall current.
- Motor power wiring is **not** provided. Do not route motor current through the breadboard, ESP32 or GPIO.
- No Wi-Fi, MQTT or motor control in this phase. Those belong to later phases.
- Records are timestamped on the laptop in UTC; `uptime_ms` is ESP32 time since boot.
- Data may be incomplete when the serial port disconnects; capture errors are reported rather than silently hidden.

## Record format
```json
{"schema_version":1,"device_id":"motor-001","seq":1,"uptime_ms":1234,"ax_mps2":0.12,"ay_mps2":0.03,"az_mps2":9.80,"temp_c":25.5,"bus_v":12.01,"current_ma":100.0,"adxl345_valid":true,"ds18b20_valid":true,"ina219_valid":true,"valid":true}
```
Numbers above are examples only.

## Definition of done
- [ ] All sensors detected and validated with motor disconnected
- [ ] Ten-minute CSV recorded with valid timestamps and sequence IDs
- [ ] Exact hardware part numbers, photos, electrical schematic and measurements documented
- [ ] Safe motor test only after independent power/current/guarding review
- [ ] Baseline measurements and known limitations recorded

## Physical bench preparation

The [physical connection preparation pack](docs/physical-connection-pack/README.md) maps all 30 product categories to bench roles, provides the GPIO21/22/4 sensor schedule and separates optional equipment, instruments and spares. It uses the newer 19 November GitHub sourcing requirements, with the user reporting ordered hardware on 20 November. Exact board and motor-power compatibility still require confirmation before energizing.

**Fixed hardware scope (user instruction, 20 November 2026): use the same 30 already selected/ordered products from the GitHub list. No replacement components or additional hardware are authorized. Preserve the existing identifiers and record unresolved connection compatibility without substituting parts.**
