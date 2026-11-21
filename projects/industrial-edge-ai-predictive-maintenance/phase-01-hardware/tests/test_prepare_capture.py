"""Offline synthetic fixtures only; no serial ports or hardware are accessed."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = load('prepare_capture', ROOT / 'scripts/prepare_capture.py')
serial_capture = load('serial_capture', ROOT / 'scripts/capture_serial.py')
contract = load('v2_contract', ROOT.parent / 'enterprise-architecture/contracts/tests/test_telemetry_v2_contract.py')
MAPPING = dict(profile='edgeops.serial-attachment.v1', site_id='synthetic-lab', asset_id='fixture-motor',
               device_id='fixture-esp32', v1_device_id='motor-001', serial_port='NOT-CONNECTED',
               board_reference='synthetic-fixture', configuration_ref='fixture-only', source_type='synthetic',
               physical_verification='unverified', calibration='not_verified', transport='usb-serial')
ROW = dict(zip(adapter.FIELDS, ['2026-11-20T10:00:00+00:00', 'motor-001', '1', '1000',
                              '0', '-0.2', '9.8', '25', '12', '125', 'True', 'True', 'True', 'True']))


def capture(rows, fields=adapter.FIELDS):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


class PrepareCaptureTests(unittest.TestCase):
    def test_fragmented_capture_to_evidence_handoff(self):
        import contextlib
        values = {key: value for key, value in ROW.items() if key != 'gateway_utc'}
        for key in ('seq', 'uptime_ms'): values[key] = int(values[key])
        for key in serial_capture.NUMERIC: values[key] = float(values[key])
        for key in ('adxl345_valid', 'ds18b20_valid', 'ina219_valid', 'valid'): values[key] = values[key] == 'True'
        values['schema_version'] = 1
        raw = (json.dumps(values) + '\n').encode()
        chunks = [raw[:20], b'', raw[20:]]
        class Port:
            def readline(self, size): return chunks.pop(0)
        ticks = iter([0, 0, 0, 0, 99])
        stream = io.StringIO(newline='')
        with contextlib.redirect_stdout(io.StringIO()):
            serial_capture.capture_stream(Port(), stream, 1, monotonic=lambda: next(ticks), receipt=lambda: ROW['gateway_utc'])
        records, rejected, _, _ = adapter.normalize(stream.getvalue().encode(), MAPPING)
        self.assertEqual(rejected, [])
        self.assertEqual(contract.failures(records[0]), [])
        self.assertEqual(records[0]['measurements']['current_a'], 0.125)

    def test_units_zero_and_provenance_match_contract(self):
        result, _ = adapter.convert(ROW, MAPPING)
        self.assertEqual(result['measurements']['current_a'], 0.125)
        self.assertEqual(result['measurements']['acceleration_x_mps2'], 0)
        self.assertIsNone(result['boot_id'])
        self.assertIsNone(result['timestamp']['device_time_utc'])
        self.assertEqual(contract.failures(result), [])

    def test_invalid_groups_are_null_and_valid_zero_survives(self):
        for sensor in ('adxl345', 'ds18b20', 'ina219'):
            row = dict(ROW, **{sensor + '_valid': 'False', 'valid': 'False'})
            result, _ = adapter.convert(row, MAPPING)
            self.assertEqual(contract.failures(result), [])
            for field in contract.CHANNELS[sensor]:
                self.assertIsNone(result['measurements'][field])
        result, _ = adapter.convert(dict(ROW, current_ma='0'), MAPPING)
        self.assertEqual(result['measurements']['current_a'], 0)

    def test_malformed_values_are_quarantined(self):
        for key, value in [('current_ma', 'NaN'), ('current_ma', '1_000'), ('current_ma', '1e999'),
                           ('seq', '-1'), ('seq', '4294967296'), ('uptime_ms', '1.0'),
                           ('valid', 'false'), ('valid', 'False'), ('device_id', 'unknown'),
                           ('gateway_utc', '2026-11-20T10:00:00')]:
            with self.subTest(key=key, value=value):
                accepted, rejected, _, count = adapter.normalize(capture([dict(ROW, **{key: value})]), MAPPING)
                self.assertEqual((accepted, len(rejected), count), ([], 1, 1))

    def test_reset_duplicate_and_clock_regression_latch_quarantine(self):
        for changes in ({'seq': '1'}, {'seq': '2', 'uptime_ms': '999'},
                        {'seq': '2', 'gateway_utc': '2026-11-20T09:59:59Z'}):
            rows = [ROW, dict(ROW, **changes), dict(ROW, seq='3', uptime_ms='3000')]
            accepted, rejected, _, _ = adapter.normalize(capture(rows), MAPPING)
            self.assertEqual((len(accepted), len(rejected)), (1, 2))
            self.assertTrue(all('discontinuity' in item['reason'] for item in rejected))

    def test_gaps_are_counted_without_inventing_boot_identity(self):
        accepted, rejected, gaps, _ = adapter.normalize(capture([ROW, dict(ROW, seq='4', uptime_ms='4000')]), MAPPING)
        self.assertEqual((len(accepted), rejected, gaps), (2, [], 2))
        self.assertTrue(all(item['boot_id'] is None for item in accepted))

    def test_exact_header_and_row_shape(self):
        for raw in (b'bad,header\n1,2\n', capture([ROW]).replace(b'gateway_utc,', b'seq,', 1)):
            with self.assertRaises(ValueError):
                adapter.normalize(raw, MAPPING)
        accepted, rejected, _, _ = adapter.normalize(capture([ROW]).rstrip() + b',extra\n', MAPPING)
        self.assertEqual((accepted, len(rejected)), ([], 1))

    def test_attachment_cannot_assert_physical_or_calibration_verification(self):
        for changes in ({'physical_verification': 'verified'}, {'calibration': 'verified'},
                        {'source_type': 'automatic'}, {'extra': 'field'}):
            with self.assertRaises(ValueError):
                adapter.attachment(dict(MAPPING, **changes))
        for declared in ('measured', 'replayed'):
            item, _ = adapter.convert(ROW, adapter.attachment(dict(MAPPING, source_type=declared)))
            self.assertEqual(contract.failures(item), [])
            self.assertEqual(item['quality']['session_quality'], 'unavailable')

    def package(self, root, rows):
        source = root / 'capture.csv'; source.write_bytes(capture(rows))
        mapping = root / 'mapping.json'; mapping.write_bytes(adapter.json_bytes(MAPPING))
        destination = root / 'evidence'
        manifest = adapter.prepare(source, mapping, destination)
        return source, mapping, destination, manifest

    def test_package_reconciles_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            source, mapping, destination, manifest = self.package(Path(temp), [ROW])
            self.assertEqual(adapter.verify(destination), manifest)
            self.assertFalse(manifest['production_ready'])
            before = (destination / 'manifest.json').read_bytes()
            with self.assertRaises(ValueError):
                adapter.prepare(source, mapping, destination)
            self.assertEqual((destination / 'manifest.json').read_bytes(), before)

    def test_tamper_and_rehashed_transformation_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, destination, manifest = self.package(Path(temp), [ROW])
            file = destination / 'observations.jsonl'
            record = json.loads(file.read_bytes()); record['measurements']['current_a'] = 999
            file.write_bytes(adapter.json_bytes(record))
            with self.assertRaises(ValueError): adapter.verify(destination)
            manifest['files'][file.name] = {'bytes': file.stat().st_size, 'sha256': adapter.sha(file.read_bytes())}
            (destination / 'manifest.json').write_bytes(adapter.json_bytes(manifest))
            with self.assertRaises(ValueError): adapter.verify(destination)

    def test_empty_input_requires_review(self):
        with tempfile.TemporaryDirectory() as temp:
            _, _, _, manifest = self.package(Path(temp), [])
            self.assertTrue(manifest['requires_review'])
            self.assertEqual(manifest['accepted_rows'], 0)

    def test_cli_exit_status_separates_preparation_from_integrity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'capture.csv'; source.write_bytes(capture([dict(ROW, valid='False')]))
            mapping = root / 'mapping.json'; mapping.write_bytes(adapter.json_bytes(MAPPING))
            output = root / 'review'
            command = [sys.executable, str(ROOT / 'scripts/prepare_capture.py')]
            prepared = subprocess.run(command + ['prepare', '--input', str(source), '--attachment', str(mapping), '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(prepared.returncode, 2, prepared.stderr)
            verified = subprocess.run(command + ['verify', str(output)], capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertTrue(json.loads(verified.stdout)['requires_review'])


if __name__ == '__main__':
    unittest.main()
