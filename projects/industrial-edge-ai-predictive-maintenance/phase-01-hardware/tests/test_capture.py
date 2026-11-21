import importlib.util
import json
import csv
import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "capture_serial.py"
spec = importlib.util.spec_from_file_location("capture_serial", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

GOOD = {
    "schema_version": 1, "device_id": "motor-001", "seq": 1, "uptime_ms": 1000,
    "ax_mps2": 0.1, "ay_mps2": 0.2, "az_mps2": 9.8,
    "temp_c": 25.0, "bus_v": 12.0, "current_ma": 100.0,
    "adxl345_valid": True, "ds18b20_valid": True, "ina219_valid": True, "valid": True,
}

class CaptureTests(unittest.TestCase):
    def stream(self, chunks):
        class Port:
            def readline(self, size):
                self.size = size
                value = chunks.pop(0)
                if isinstance(value, Exception): raise value
                return value
        ticks = iter([0] + [0] * len(chunks) + [99])
        output = io.StringIO(newline='')
        with contextlib.redirect_stdout(io.StringIO()):
            result = module.capture_stream(Port(), output, 1, monotonic=lambda: next(ticks),
                                           receipt=lambda: '2026-11-20T10:00:00+00:00')
        return result, list(csv.DictReader(io.StringIO(output.getvalue())))

    def frame(self, **changes):
        return (json.dumps(dict(GOOD, **changes)) + '\n').encode()

    def test_valid_record(self):
        self.assertEqual(module.parse_record(json.dumps(GOOD))["seq"], 1)

    def test_reject_wrong_schema(self):
        value = dict(GOOD, schema_version=2)
        with self.assertRaises(ValueError):
            module.parse_record(json.dumps(value))

    def test_reject_nonfinite(self):
        value = dict(GOOD, current_ma=float("nan"))
        with self.assertRaises(ValueError):
            module.parse_record(json.dumps(value))

    def test_reject_invalid_flags(self):
        value = dict(GOOD, valid=False)
        with self.assertRaises(ValueError):
            module.parse_record(json.dumps(value))

    def test_strict_schema_counters_identifiers_and_duplicate_keys(self):
        for changes in ({'schema_version': True}, {'seq': 4294967296}, {'uptime_ms': -1},
                        {'device_id': 'bad id'}, {'unknown': 1}, {'current_ma': 10**400}):
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValueError): module.parse_record(json.dumps(dict(GOOD, **changes)))
        with self.assertRaises(ValueError):
            module.parse_record(json.dumps(GOOD).replace('"seq": 1', '"seq": 1, "seq": 2'))

    def test_timeout_fragments_reassemble_without_losing_record(self):
        raw = self.frame()
        counts, rows = self.stream([raw[:40], b'', raw[40:]])
        self.assertEqual((counts['records'], counts['invalid'], len(rows)), (1, 0, 1))
        self.assertEqual(rows[0]['current_ma'], '100.0')

    def test_partial_final_record_is_not_written(self):
        counts, rows = self.stream([self.frame().rstrip(b'\n')])
        self.assertEqual((counts['records'], counts['invalid'], rows), (0, 1, []))

    def test_oversize_is_drained_before_next_frame(self):
        counts, rows = self.stream([b'x' * (module.MAX_LINE_BYTES + 1), b'tail\n', self.frame()])
        self.assertEqual((counts['records'], counts['invalid'], len(rows)), (1, 1, 1))

    def test_bad_utf8_and_malformed_json_do_not_hide_next_record(self):
        counts, rows = self.stream([b'\xff\n', b'{bad}\n', self.frame()])
        self.assertEqual((counts['records'], counts['invalid'], len(rows)), (1, 2, 1))

    def test_sensor_invalid_and_counter_resets_are_separate(self):
        counts, rows = self.stream([self.frame(), self.frame(seq=4, uptime_ms=4000),
                                   self.frame(seq=0, uptime_ms=0, ina219_valid=False, valid=False)])
        self.assertEqual((counts['records'], counts['sensor_invalid'], counts['sequence_gaps'], counts['discontinuities']), (3, 1, 2, 1))
        self.assertEqual(rows[-1]['ina219_valid'], 'False')

    def test_disconnect_preserves_flushed_prefix(self):
        chunks = [self.frame(), OSError('disconnected')]
        class Port:
            def readline(self, size):
                value = chunks.pop(0)
                if isinstance(value, Exception): raise value
                return value
        output = io.StringIO(newline='')
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(OSError):
            module.capture_stream(Port(), output, 1, monotonic=lambda: 0)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(output.getvalue())))), 1)

    def test_existing_capture_is_refused_before_import_or_port_open(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'saved.csv'; path.write_bytes(b'original')
            with patch.object(sys, 'argv', ['capture_serial.py', '--port', 'NOT-CONNECTED', '--output', str(path)]), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result: module.main()
            self.assertEqual(result.exception.code, 1)
            self.assertEqual(path.read_bytes(), b'original')

    def test_failed_connection_returns_failure_without_replacing_evidence(self):
        class SerialError(Exception): pass
        def fail(*args, **kwargs): raise SerialError('offline simulation')
        fake = types.SimpleNamespace(Serial=fail, SerialException=SerialError)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'new.csv'
            with patch.dict(sys.modules, {'serial': fake}), patch.object(sys, 'argv', ['capture_serial.py', '--port', 'NOT-CONNECTED', '--output', str(path)]), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 1)
            self.assertEqual(path.read_bytes(), b'')

if __name__ == "__main__":
    unittest.main()
