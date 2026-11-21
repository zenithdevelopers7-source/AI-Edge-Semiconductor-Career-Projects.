#!/usr/bin/env python3
"""Capture ESP32 JSON Lines telemetry to CSV with basic schema checks."""
import argparse
import csv
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

FIELDS = [
    "gateway_utc", "device_id", "seq", "uptime_ms", "ax_mps2",
    "ay_mps2", "az_mps2", "temp_c", "bus_v", "current_ma",
    "adxl345_valid", "ds18b20_valid", "ina219_valid", "valid",
]
NUMERIC = ("ax_mps2", "ay_mps2", "az_mps2", "temp_c", "bus_v", "current_ma")

MAX_LINE_BYTES = 4096


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def parse_record(line):
    obj = json.loads(line, object_pairs_hook=unique_object)
    expected = (set(FIELDS) - {"gateway_utc"}) | {"schema_version"}
    if not isinstance(obj, dict) or set(obj) != expected:
        raise ValueError("unexpected record fields")
    if type(obj.get("schema_version")) is not int or obj["schema_version"] != 1:
        raise ValueError("unsupported schema")
    if not isinstance(obj.get("device_id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", obj["device_id"]):
        raise ValueError("missing device_id")
    for key in ("seq", "uptime_ms"):
        if type(obj.get(key)) is not int or not 0 <= obj[key] <= 4294967295:
            raise ValueError(f"invalid {key}")
    for key in NUMERIC:
        value = obj.get(key)
        if type(value) not in (int, float) or abs(value) > sys.float_info.max or not math.isfinite(value):
            raise ValueError(f"invalid {key}")
    for key in ("adxl345_valid", "ds18b20_valid", "ina219_valid", "valid"):
        if type(obj.get(key)) is not bool:
            raise ValueError(f"invalid {key}")
    if obj["valid"] != (obj["adxl345_valid"] and obj["ds18b20_valid"] and obj["ina219_valid"]):
        raise ValueError("inconsistent validity flags")
    return {k: obj[k] for k in FIELDS if k != "gateway_utc"}

def capture_stream(port, file, seconds, monotonic=time.monotonic,
                   receipt=lambda: datetime.now(timezone.utc).isoformat()):
    """Read bounded chunks; preserve only complete, validated V1 records.

    Injected ports/clocks allow offline tests. Counts describe captured records,
    not physical measurement validity, authenticated sessions or packet loss.
    """
    counts = dict(records=0, invalid=0, sensor_invalid=0, sequence_gaps=0, discontinuities=0)
    writer = csv.DictWriter(file, fieldnames=FIELDS)
    writer.writeheader()
    file.flush()
    previous = {}
    pending = bytearray()
    discarding = False
    start = monotonic()
    try:
        while monotonic() - start < seconds:
            raw = port.readline(MAX_LINE_BYTES + 1)
            if not raw:
                continue  # A timeout is not a record boundary.
            if discarding:
                if raw.endswith(b"\n"):
                    discarding = False
                continue
            pending.extend(raw)
            if len(pending) > MAX_LINE_BYTES:
                counts["invalid"] += 1
                pending.clear()
                discarding = not raw.endswith(b"\n")
                continue
            if not pending.endswith(b"\n"):
                continue
            try:
                line = pending.decode("utf-8").strip()
                pending.clear()
                if not line or line.startswith("#"):
                    continue
                record = parse_record(line)
            except (ValueError, UnicodeError, RecursionError):
                pending.clear()
                counts["invalid"] += 1
                continue
            prior = previous.get(record["device_id"])
            if prior is not None:
                if record["seq"] <= prior[0] or record["uptime_ms"] < prior[1]:
                    counts["discontinuities"] += 1
                else:
                    counts["sequence_gaps"] += max(0, record["seq"] - prior[0] - 1)
            previous[record["device_id"]] = (record["seq"], record["uptime_ms"])
            record["gateway_utc"] = receipt()
            writer.writerow(record)
            file.flush()
            counts["records"] += 1
            if not record["valid"]:
                counts["sensor_invalid"] += 1
    finally:
        if pending:
            counts["invalid"] += 1
        print(json.dumps(counts, sort_keys=True))
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="e.g. /dev/cu.usbserial-XXXX or COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--output", default="data/baseline.csv")
    args = parser.parse_args()
    if not 0 < args.seconds <= 86400:
        parser.error("--seconds must be between 1 and 86400")
    if args.baud <= 0:
        parser.error("--baud must be positive")
    out = Path(args.output)
    if out.exists() or out.is_symlink():
        parser.exit(1, "Capture refused: choose a new output filename; existing evidence is never overwritten.\n")
    try:
        import serial
    except ImportError:
        parser.exit(1, "Install dependencies: python -m pip install -r scripts/requirements.txt\n")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation occurs before opening the port, including race cases.
        with out.open("x", newline="", encoding="utf-8") as file:
            with serial.Serial(args.port, args.baud, timeout=1) as port:
                counts = capture_stream(port, file, args.seconds)
        if counts["records"] == 0:
            print("No complete valid-format records were captured; retain the file for review.", file=sys.stderr)
            return 2
    except KeyboardInterrupt:
        print("Capture interrupted; any saved CSV is partial and requires review.", file=sys.stderr)
        return 130
    except (OSError, serial.SerialException):
        print("Capture stopped: output unavailable or serial connection failed. Any saved CSV is partial and requires review.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
