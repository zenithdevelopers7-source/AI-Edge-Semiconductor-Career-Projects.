"""Build-record fixtures are dummy bytes, not firmware or physical test evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/record_firmware_build.py'
spec = importlib.util.spec_from_file_location('firmware_record', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class BuildRecordTests(unittest.TestCase):
    def fixture(self, root):
        for name in module.SOURCES + module.ARTIFACTS:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'not firmware: synthetic inventory test')

    def test_inventory_hashes_do_not_assert_build_success_or_hardware_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            with patch.object(module.importlib.metadata, 'version', return_value='fixture-only'):
                data = module.record(root)
            self.assertNotIn('build_success', data)
            self.assertTrue(all(data[name] is False for name in ('hardware_connected','firmware_uploaded','calibration_verified','production_ready')))
            for name, entry in data['files'].items():
                raw = (root / name).read_bytes()
                self.assertEqual(entry, {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    def test_missing_or_empty_artifact_refuses_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); self.fixture(root)
            path = root / module.ARTIFACTS[0]; path.write_bytes(b'')
            with self.assertRaises(ValueError): module.record(root)
            path.unlink()
            with self.assertRaises(ValueError): module.record(root)

    def test_existing_record_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / 'scripts').mkdir(); (root / 'firmware').mkdir()
            record = root / 'firmware/build-evidence.json'; record.write_bytes(b'original')
            with patch.object(module, '__file__', str(root / 'scripts/record_firmware_build.py')), patch.object(module, 'record', return_value={'fixture': True}):
                self.assertEqual(module.main(), 1)
            self.assertEqual(record.read_bytes(), b'original')


if __name__ == '__main__': unittest.main()
