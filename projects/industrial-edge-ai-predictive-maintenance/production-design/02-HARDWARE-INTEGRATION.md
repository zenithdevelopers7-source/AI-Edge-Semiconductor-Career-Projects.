# 02 — All 30 Hardware Categories and Physical Integration

**Basis:** existing [30-category register](../HARDWARE_30_PRODUCT_REGISTER.md) and [end-to-end hardware report](../INDUSTRIAL_EDGE_AI_30_HARDWARE_END_TO_END_REPORT.md). **Status:** functional integration design; not an approved electrical schematic or verified purchase inventory.

## 1. Inventory identity and lifecycle

Use design identifiers **BOM-01 … BOM-30**, preserving the original register order. An individual installed part receives a separate `hardware_instance_id`, exact maker/part/revision/serial, ratings, datasheet revision/hash, supplier/order reference, test evidence, location and installation/retirement history. A BOM category is not a unique physical device or proof of ownership.

The dashboard's old `HW-01 … HW-14` are grouped planning labels. Some combine several BOM categories; their numbers do not match this list. Preserve those records as legacy aliases and explicitly map them to BOM categories. Never overwrite HW-07 with BOM-07 or infer that 14 named groups means exactly 14 of 30 products were purchased. The preceding chat identifies a selected connector variant, not verified delivery of a full kit.

Procurement states: planned → selected/cart → ordered → received → inspected → commissioned → retired; blocked/rejected are explicit dispositions. Purchase and commissioning facts need evidence. All quantities and exact variants below remain to be reconciled with actual parts.

## 2. Complete hardware-to-system traceability

| ID | Hardware category | Lifecycle role and physical connection | Software/data/workspace relationship | Required acceptance evidence |
|---|---|---|---|---|
| BOM-01 | Raspberry Pi 5, 4 GB | Installed edge host; dedicated compatible supply and private LAN | Broker, durable edge agent, feature/inference services; Device/Edge Health | Board/OS identity, boot, thermal/resource tests, outage/restart/spool evidence |
| BOM-02 | ESP32-WROOM-32 development board | Installed acquisition controller; sensor I2C/OneWire and reviewed USB power | Firmware/device registry, boot/sequence/quality, enrollment and diagnostics | Exact module/board, firmware build, pin/voltage checks, sensor-only logs and unique identity |
| BOM-03 | ADXL345 accelerometer | Rigid, repeatable motor-housing mounting; 3.3 V-compatible I2C | Acceleration channels in m/s², raw windows/features and calibration records | Address/straps, orientation/range, measured sample timing, clipping/noise and mounting repeatability |
| BOM-04 | DS18B20 probe | Motor-case contact; three-wire powered configuration, GPIO4 reference | Casing temperature and validity/age; Telemetry and Sensor Quality | Exact probe wiring, pull-up, completed conversion/CRC where supported, reference comparison and attachment |
| BOM-05 | INA219 DC monitor | Rated high-side DC input measurement path only after shunt/module review | DC bus voltage, input current and derived power; electrical sensor quality | Shunt value/power, terminals/PCB rating, startup suitability, calibration and reference readings |
| BOM-06 | 12 V DC motor | Rigid mount with guarded moving parts and supervised local operating controls | Asset identity, operating sessions and maintenance evidence | Exact motor variant, rated/startup/stall information from maker, reviewed safe operating envelope |
| BOM-07 | Regulated 12 V motor supply, register target 5 A | Separate protected motor power domain; enclosed mains adapter | Power-domain BOM and commissioning record; no direct network telemetry | Manufacturer rating/protection, polarity, connector/load suitability; 3 A/5 A remains undecided until motor-path review |
| BOM-08 | Official/compatible Pi 5 USB-C supply | Dedicated Pi power, independent of motor circuit | Edge undervoltage/restart evidence and supply identity | Compatible profile/cable, no undervoltage during measured load and attached-peripheral budget |
| BOM-09 | Pi 5 case | Fits board, ports and cooler; non-obstructed ventilation | Mechanical installation and maintenance record | Fit, cable clearance, airflow and access review |
| BOM-10 | Pi 5 active cooler | Correct board fan connector and mechanical installation | Edge temperature/throttling and inference performance evidence | Correct fit/control, stress temperature and throttling observations |
| BOM-11 | 64 GB microSD | Edge OS and bounded spool/capture storage; endurance assessed | Disk quotas, filesystem health, logs and boot recovery | Actual capacity/endurance, image verification, growth/power-loss/restart and backup tests |
| BOM-12 | Breadboard | Sensor-only commissioning; removed from motor-current path | Bring-up configuration and wiring evidence, not a live asset | Continuity and low-current-only use; final installed wiring reviewed separately |
| BOM-13 | Dupont jumper wires | Short low-current sensor connections during bring-up | Bus reliability and wiring revision references | Pin continuity, secure connection and bus-error/jitter evidence; replace weak final connections as needed |
| BOM-14 | ESP32 USB data cable | Firmware upload, serial capture and commissioning power where approved | Firmware release trace and serial fallback transport | Data capability, stable device enumeration and uninterrupted capture |
| BOM-15 | Digital multimeter | Commissioning/maintenance reference instrument, not permanently inline | Calibration/inspection records and uploaded measurements | Instrument identification/range, polarity/continuity/reference checks and appropriate measurement method |
| BOM-16 | 4.7 kΩ resistor assortment | DS18B20 DATA pull-up to reviewed 3.3 V logic rail | Wiring/configuration register; no own telemetry channel | Resistance/placement and stable OneWire behavior with actual cable/bus |
| BOM-17 | 5.5 × 2.1 mm male/female DC terminal connectors | Matching DC adapter interface; mechanical strain relief | Connector specification and inspection record | Actual dimensions/polarity, verified DC current rating, contact heating/pull-test within safe procedure |
| BOM-18 | DC inline fuse holder and fuse | Motor branch protection located by reviewed source/distribution design | Safety inspection and replacement record | DC breaking/current/time characteristic, fault-energy/wire coordination and holder rating, selected by reviewer |
| BOM-19 | Rated DC isolation switch | Accessible local motor supply disconnect independent of software | Inspection evidence only; displayed state is unverified without a separate feedback sensor | DC switching rating, accessible mounting and independent functional verification |
| BOM-20 | Motor shaft safety guard | Covers rotating parts with adequate clearance and secure fixing | Mechanical safety inspection/maintenance evidence | Actual fit, fastening, clearance and protection review; no invented guard-closed telemetry |
| BOM-21 | Rated motor driver or MOSFET module | Locally supervised motor-power subsystem; not exposed through cloud/AI GPIO commands | Driver identity/configuration, local test-session operating condition | Full board/current/thermal/startup review; TB6612FNG only if compatible, otherwise replace by rated design |
| BOM-22 | Flyback diode / TVS suppression | Topology-dependent transient protection following driver/reference circuit | Reviewed electrical schematic and component inspection | Correct topology/polarity/energy rating; H-bridge recirculation/braking compatibility |
| BOM-23 | Hook-up wires and ferrules | Motor DC wiring and secure terminal terminations, sized for actual circuit | Wire schedule, installation revision and inspection results | Gauge/insulation/current/temperature/termination review and safe pull-test |
| BOM-24 | DC terminal distribution blocks | Covered/labeled low-voltage distribution and measurement/service points | Power-domain connection register and commissioning record | Rated terminals, enclosure, polarity, spacing, fastening and strain relief |
| BOM-25 | Motor mounting bracket/base | Holds motor and sensor reference position repeatably | Asset setup revision and recording-session configuration | Structural stability, fixing, guard integration and repeatable sensor orientation |
| BOM-26 | 12 V → 5 V buck converter | Conditional, separately fused auxiliary peripheral branch only if needed | Auxiliary power configuration and inspection; normally not Pi's primary supply | Output/ripple/load/polarity/thermal tests; assess grounding/backfeed; leave uninstalled if no justified load |
| BOM-27 | I2C logic-level shifter | Conditional only when an approved module requires level translation | Bus topology/config metadata and validation report | Bidirectional compatibility, pull-up/capacitance/timing checks; omit for an already 3.3 V-safe bus |
| BOM-28 | USB-to-TTL serial adapter | Commissioning/diagnostic UART with actual 3.3 V logic | Diagnostic capture provenance; distinct from enrolled device network identity | Signal level, pinout/ground and safe power isolation; prevent simultaneous power-source backfeed |
| BOM-29 | USB/DC inline power meter | Optional benchmark instrument on a compatible input path | Manually imported power/energy benchmark with meter placement and sample method | Connector/PD/pass-through/current limits and reference check; do not assume it measures all system rails |
| BOM-30 | Spare ESP32 and sensor kit | Cold spare, A/B replication and replacement commissioning | Hardware replacement history and newly enrolled board identity | Spare bring-up, configuration comparison, old credential revocation and new calibration/baseline |

**Coverage rule:** 30/30 category mappings is design coverage. It is not 30/30 received, installed or tested hardware. Instruments, spare stock and conditional components must retain honest lifecycle states in the dashboard.

## 3. Functional power domains

This is a conceptual allocation of responsibility. Do not assemble from it as a substitute for an engineered circuit drawing.

```text
Enclosed external motor adapter
  → reviewed connector/protection/disconnect/distribution
  → rated DC measurement section if qualified
  → reviewed local driver/suppression circuit → guarded, mounted motor

Dedicated Pi-compatible USB-C supply → Pi 5 → case/cooler/storage

Reviewed USB/regulated controller supply → ESP32 → reviewed 3.3 V sensor logic

Optional protected 12 V auxiliary branch → qualified buck → approved 5 V peripheral only
```

Ground/reference connections, shielding, suppression location, fuse values, conductor sizes, driver enable behavior and independent disconnect must be determined from exact parts and reviewed as one circuit. Do not route motor current through breadboards or GPIO, feed 12 V into Pi/ESP32 logic, or join multiple power sources without a reviewed backfeed/grounding design. A buck converter is not automatically an appropriate Pi USB-C/PD replacement.

A simple flyback diode arrangement for a one-direction switch is not automatically appropriate across an H-bridge motor, particularly with reverse drive or braking. Follow the chosen driver board's documented current recirculation and transient-protection topology; do not install every suppression component merely to consume the BOM.

The switch/guard have no electronic position sensors in the current register. The UI may show a dated human inspection, but must not display a live “guard closed” or “power safely isolated” signal based on assumption. Installation of monitored interlocks would be an additional reviewed hardware requirement, not an existing feature.

## 4. Signal connections and measurement meaning

Reference pins from current firmware are **GPIO21 SDA, GPIO22 SCL, GPIO4 OneWire**, subject to the exact DevKit/breakout pinout and board revision. ADXL345 and INA219 share a reviewed 3.3 V-safe I2C bus. Confirm addresses, CS/address straps, existing parallel pull-ups, cable length and rise time. Temperature conversion must not block timed accelerometer collection.

ADXL345 measures acceleration, not velocity. Record raw x/y/z m/s² and separately defined gravity-removal/window features; do not relabel them mm/s. DS18B20 provides a probe/case measurement, not inferred winding temperature. INA219 on the driver's DC input measures input-bus current, which is not identical to instantaneous PWM winding current; label placement and filtering. Instantaneous P=V×I or interval energy estimates need matched sampling and documented assumptions.

The current firmware emits one record/s and does not compute high-rate RMS/FFT. A **candidate** enhanced acquisition mode uses 400 samples/s for acceleration and 2-second windows with a 1-second step, conditional on bus, firmware and sensor validation. Official ADXL345 documentation relates usable I2C output rate to bus speed; 100 kHz does not justify the higher candidate rate. Reconfigure and verify the entire shared bus before claiming it. Maintain slower independent thermal/electrical schedules and per-channel age. No FFT/bearing-band claim is valid until bandwidth, anti-alias behavior, timing, sample completeness and mounting are demonstrated.

## 5. Compatibility decisions still requiring exact parts

- The chat mentions GA25-370 12 V 170 RPM and TB6612FNG candidates. These names do not establish exact motor stall current or board current/thermal capability. Do not size the circuit by the adapter's 3 A/5 A label alone. Toshiba's IC peak rating has pulse conditions; it is not a continuous board rating.
- TI's INA219 IC operating envelope does not establish the current/thermal rating of an unknown breakout's shunt, terminals or PCB. Qualify the complete measurement path or use a suitable rated alternative under a hardware-change decision.
- Check lifecycle/support for the exact ESP32 module before production procurement. The legacy ESP32-WROOM-32 documentation is marked not recommended for new designs; an existing DevKit can remain a lab source while a supported production variant is assessed through an explicit compatibility decision.
- Pi 5 must use a compatible independently powered configuration with an actual peripheral budget. Record power-meter insertion effects if measuring USB-C power.
- The register lacks exact supplier part numbers, decoupling/passive details, final enclosure and all supporting infrastructure. These remain a final engineered-BOM task; the 30 categories are not a fabrication-ready parts list.

## 6. Hardware acceptance sequence

1. Reconcile receipts/physical labels, quantity, maker datasheets and unique instances against all 30 categories; mark planned/conditional/spare separately.
2. Review the sensor-only 3.3 V circuit and actual pinout. Verify supply/polarity and sensor response with motor power disconnected.
3. Complete reference comparisons, per-channel validity, timing and repeated ten-minute sensor sessions; record effective rates and raw evidence.
4. Obtain a qualified review of the exact motor-power/driver/measurement/protection/guard/mount design. Motor startup/stall ratings should come from reliable specifications or an appropriately controlled engineering method; do not deliberately stall the motor as a chat-guided test.
5. Perform supervised guarded healthy runs within accepted limits; document setup, local operating condition, supply stability and sensor mounting.
6. Commission Pi/broker/edge identity, power/thermal/storage behavior and recovery; correlate data back to physical hardware instances.
7. Exercise spare replacement and firmware/model compatibility without reusing another board's credentials or silently merging calibration histories.

## 7. Primary engineering references

These references establish device-level facts, not approval of unknown marketplace modules:

- [Analog Devices ADXL345 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf) — output units/interfaces, bus-rate limits, sensor configuration.
- [Analog Devices DS18B20 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf) — powered interface and conversion behavior.
- [Texas Instruments INA219](https://www.ti.com/product/INA219) — electrical-monitor IC; board/shunt limits require separate evidence.
- [Toshiba TB6612FNG product and datasheet](https://toshiba.semicon-storage.com/eu/semiconductor/product/general-purpose-logic-ics/detail.TB6612FNG.html) — current/thermal/pulse constraints of the IC.
- [Raspberry Pi power documentation](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) — compatible Pi supply/peripheral power requirements.
- [Espressif ESP32-WROOM-32 documentation](https://documentation.espressif.com/esp32-wroom-32_datasheet_en.html) — module identity/electrical characteristics and lifecycle status.
