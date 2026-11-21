# Wiring and Safety — ESP32 Sensor-Only Test

**Do not connect the motor during initial sensor bring-up.** This is a connection table, **not** a reviewed electrical schematic.

| ESP32 DevKit | ADXL345 breakout | INA219 breakout | DS18B20 |
|---|---|---|---|
| 3V3 | VCC only if module supports 3.3V | VCC only if module supports 3.3V | VDD |
| GND | GND | GND | GND |
| GPIO21 | SDA | SDA | — |
| GPIO22 | SCL | SCL | — |
| GPIO4 | — | — | DATA |

- DS18B20: 4.7 kOhm pull-up between DATA and 3.3V. Confirm package pinout.
- ADXL345: verify breakout-specific I2C mode selection (CS and SDO/ALT ADDRESS), pull-ups, address and voltage requirements.
- INA219: verify shunt rating, bus voltage, current calibration and electrical isolation before connecting any load. This starter reads an appropriately rated **low-current DC measurement path only**.
- ESP32 GPIO is 3.3V logic; never apply 5V signals directly.
- Check polarity and voltage with a multimeter before powering.
- Motor requires a separate reviewed circuit, rated supply/driver, appropriate protection, secure mount, rotating-parts guard and manual emergency disconnect.
- Do not run mains voltage or motor current through breadboards or ESP32 pins.
- Never intentionally jam, stall, or damage a rotating motor to produce anomaly labels.

## Validation record template
Record exact module manufacturers/part numbers, photos, wiring diagram, measured voltages, detected I2C addresses, sensor mounting, ambient conditions, test date, sampling interval, valid-record rate, sequence gaps, and observed limitations.

## Physical preparation pack

Use [the 30-product physical preparation pack](physical-connection-pack/README.md) and its printable guide/connection matrix. It is based on the newer GitHub sourcing table, preserves the sensor-only pin map and explicitly identifies motor/driver ratings that are still unresolved. It does not assign a motor-power circuit or commission equipment.
