"""Record hashes after a successful compile; this script is not a compiler or acceptance verifier."""
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

SOURCES = ('firmware/platformio.ini', 'firmware/src/main.cpp', 'requirements-build.txt')
ARTIFACTS = tuple('firmware/.pio/build/esp32dev/' + name for name in
                  ('firmware.bin', 'firmware.elf', 'bootloader.bin', 'partitions.bin'))


def record(root):
    root = Path(root)
    entries = {}
    for name in SOURCES + ARTIFACTS:
        path = root / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 16 * 1024 * 1024:
            raise ValueError('Missing, linked, empty or oversized build input/artifact')
        data = path.read_bytes()
        entries[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    return {'format': 'edgeops-esp32-build-record-v1', 'recorded_at': datetime.now(timezone.utc).isoformat(),
            'target': 'esp32dev', 'python_version': sys.version.split()[0],
            'platformio_version': importlib.metadata.version('platformio'),
            'scope': 'hash inventory only; successful compilation must be established by the build job',
            'hardware_connected': False, 'firmware_uploaded': False, 'calibration_verified': False,
            'production_ready': False, 'files': entries}


def main():
    root = Path(__file__).resolve().parents[1]
    try:
        data = record(root)
        with (root / 'firmware/build-evidence.json').open('x', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2); stream.write('\n')
    except (OSError, ValueError, importlib.metadata.PackageNotFoundError):
        print('Build record refused: install the build tool, compile first and choose a fresh evidence location.', file=sys.stderr)
        return 1
    print('Recorded hashes for the existing ESP32 target; no upload or hardware acceptance.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
