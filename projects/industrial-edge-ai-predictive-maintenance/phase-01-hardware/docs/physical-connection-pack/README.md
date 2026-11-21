# Physical connection preparation pack - 20 November 2026

Basis: the [newer GitHub 30-product sourcing table](https://github.com/zenithdevelopers7-source/AI-Edge-Semiconductor-Career-Projects./blob/b2c327be2841b2b2faa9055d8240b1feb4b6e7b0/projects/industrial-edge-ai-predictive-maintenance/HARDWARE_30_PRODUCTS_TEMU_SOURCING.md), not the older blanket 12V/5A assumption. The user reports hardware ordered; actual received board revisions, current ratings and wiring have not been verified. P01-P30 correspond to the existing BOM-01-BOM-30 category numbers. This pack prepares physical layout and a conditional sensor wire schedule. It does not certify a motor-power circuit or mark anything connected in software.

## Fixed hardware scope - user instruction, 20 November 2026

Use the same 30 products already selected and ordered by the user, as listed in the GitHub hardware table. Do not recommend or substitute different boards, motors, sensors, supplies, drivers or accessories. Do not expand the list with additional hardware. Keep P01-P30 / BOM-01-BOM-30 identities unchanged. Mechanical parts, instruments, optional installation items and spares remain part of the same set, even when they are not electrically connected together.

If an ordered part has an unresolved rating or incompatible terminal arrangement, leave that specific power/connection step pending and record the issue. Do not silently replace the part or infer that the ordered combination has been verified. Ordering, receipt, connection, calibration and commissioning remain separate facts.

## 1. Lay out three separate bench zones

1. Pi zone: P01/P08/P09/P10/P11. Dedicated Pi USB-C supply, case, cooler and storage.
2. Sensor zone: P02/P03/P04/P05/P12/P13/P14/P16. Motor power disconnected. One USB source powers the ESP32; only verified 3.3V-safe sensor supply/logic joins it.
3. Motor zone: P06/P07/P17-P25 plus optional P29. Mount and guard mechanically; final power/control terminals remain pending exact-part current/driver/measurement review. No motor current passes through the breadboard or controller.

P15 is a tool. P26-P29 retain their optional installation roles within the same selected set; they are not connected merely to consume every item. P30 is a cold spare. No separate enclosure or other product outside P01-P30 is added by this connection pack.

## 2. Conditional sensor wire schedule - no motor supply

Use printed GPIO labels, not guessed physical header positions. This map matches current firmware for the classic ESP32 target. Match the actual DevKit/breakout documentation first; clone boards may label/regulate power differently.

| Wire | From | To | Condition |
| --- | --- | --- | --- |
| S01 | One computer OR Pi USB host | P14 cable -> ESP32 USB | Matching socket/data cable; no other ESP32 power source |
| S02 | ESP32 3V3 | Reviewed ADXL345 3.3V-compatible supply terminal | Check onboard regulator/input pin, not just generic VCC/VIN wording |
| S03 | ESP32 3V3 | Reviewed INA219 logic supply terminal | Logic only; load terminals remain disconnected |
| S04 | ESP32 3V3 | Verified DS18B20 VDD conductor | Supplier wire identification, not assumed colours |
| S05 | ESP32 GND | Sensor logic grounds / DS18B20 GND | Sensor-only common reference; no unreviewed motor return routing |
| S06 | ESP32 GPIO21 | ADXL345 SDA and INA219 SDA | I2C pull-ups must reference approved 3.3V logic |
| S07 | ESP32 GPIO22 | ADXL345 SCL and INA219 SCL | Shared I2C bus; inspect parallel pull-ups |
| S08 | ESP32 GPIO4 | DS18B20 DATA | Externally powered 3-wire configuration |
| S09 | DS18B20 DATA/GPIO4 | P16 effective 4.7k pull-up -> 3.3V | Do not blindly duplicate a pull-up already fitted on a module |
| S10 | ADXL345 CS / SDO | Breakout-specific I2C straps | For exposed bare sensor signals: CS -> VDD I/O; SDO -> GND selects 0x53. Follow actual board schematic; do not undo fixed straps blindly |

No connection is assigned from 12V to ESP32/Pi power or GPIO. INA219 VIN+/VIN- are not logic-supply inputs. A successful I2C response does not establish that its high-current path can carry the motor.

## 3. Motor circuit release fields

The GitHub source gives a GA25-370/JGA25-370 12V ~170RPM target and TB6612FNG **candidate**, not exact ordered board schematics or confirmed current compatibility. It calls the existing 12V/2A adapter provisional. Consequently this pack assigns no fuse value, wire gauge approval, driver control GPIO, motor output/return terminals or suppression component values.

Complete the following from labels, supplier/manufacturer data and a qualified review of the complete circuit: motor rated/start/stall current; driver board schematic/thermal capability and default-disabled local control; supply protection/polarity; INA219 shunt/PCB/terminal limits; fuse/wire/switch/connector coordination; driver-specific decoupling/recirculation; mounting/guard fit. Do not intentionally stall the motor to obtain a rating.

Functional motor path only: enclosed 12V adapter -> coordinated connector/protection/disconnect/distribution -> qualified input-current measurement if suitable -> approved local driver -> guarded motor. Return/reference routing is part of the exact schematic, not a generic instruction to join every ground. This flow is not a terminal-to-terminal assembly drawing.

The current firmware defines **no motor-control outputs**. Do not wire guessed PWM, direction or standby GPIOs. A rated local operating/control method and startup-disabled behavior must be specified with the final driver design. A normal inline switch is not an automatically certified emergency stop.

## 4. Pi and controller installation

With power removed, fit the microSD, specified cooler and compatible case. Use the Pi's dedicated fan connector for a compatible Pi 5 cooler. Power Pi from P08 through USB-C, independently of the motor circuit. Do not substitute P26 buck as its default supply.

For the current firmware path, use USB serial from ESP32 to **one** host: first a workstation, or later a configured Pi USB port. Do not connect both host power sources or external 5V/3V3 to the ESP32 at the same time. Optional P28 is unnecessary while onboard USB-UART is used. No Pi GPIO sensor bus connection is required for this design.

## 5. What can be prepared before testing

Disconnect all power. Identify every module's actual labels and cable ends; arrange the three zones; check case/cooler and bracket/guard fit without forcing screws; label the sensor wire schedule; record the ordered part variants in the CSV. Sensor wiring proceeds only after its actual voltage/pinout checks. Keep motor power isolated until the complete power/control schematic is released. Pre-power polarity/continuity/ratings checks cannot be deferred until after energizing.

## 6. Software boundary at physical handover

The current firmware uses GPIO21/22/4, I2C at 100kHz, USB serial at 115200 baud, and one V1 summary record per second. It has no Wi-Fi/MQTT or motor-control implementation. V1 flags invalid fields separately while numeric placeholders may be zero. The [offline capture handoff](../OFFLINE_CAPTURE_HANDOFF.md) now supplies an offline V1-to-candidate-V2 adapter that retains acceleration m/s2, converts current mA to A once, and maps invalid sensor groups to null. It does not authenticate physical identity or create verified boot/time provenance. The current dashboard ingestion remains synthetic-only and rejects measured claims. A reviewed measured commissioning and ingestion path is still required; plugging in boards does not automatically populate the synthetic charts.

## 7. Engineering references

- [ADXL345 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/adxl345.pdf): I2C mode/straps and IC voltage constraints; breakout supply pin still requires its own schematic.
- [DS18B20 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/DS18B20.pdf): powered three-wire interface; probe conductor identification is supplier-specific.
- [INA219 datasheet](https://www.ti.com/lit/ds/symlink/ina219.pdf): IC sensing/logic operation; this does not rate an unknown breakout's shunt or terminals.
- [ESP32-DevKitC V4 guide](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html): header labels and mutually exclusive power options; verify the actual board variant.
- [Pi 5 power/hardware](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html) and [27W supply](https://www.raspberrypi.com/products/27w-power-supply/).
- [TB6612FNG IC datasheet](https://toshiba.semicon-storage.com/info/docget.jsp?did=10660&prodName=TB6612FNG): driver modes/current/thermal limits; not approval of an unknown carrier/motor combination.

## Files

Use the printable connection-guide.html with the all-30-connection-matrix.csv. Blank inspection fields are intentionally unverified. No hardware-connected, calibration, received-item or production-acceptance state is changed by creating this pack.
