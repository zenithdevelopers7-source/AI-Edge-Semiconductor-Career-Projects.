"""Bounded, read-only export of fixed-scope preparation sources; never device control."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import zipfile

from fastapi import HTTPException
from physical_build import read_plan

HARDWARE_FILES = (
    'README.md', 'firmware/platformio.ini', 'firmware/src/main.cpp', 'requirements-build.txt',
    'scripts/record_firmware_build.py', 'tests/test_firmware_build.py', 'docs/FIRMWARE_BUILD.md',
    'scripts/capture_serial.py', 'scripts/prepare_capture.py', 'scripts/requirements.txt',
    'tests/test_capture.py', 'tests/test_prepare_capture.py', 'tests/requirements.txt',
    'examples/offline-capture/synthetic.capture.csv', 'examples/offline-capture/synthetic.attachment.json',
    'docs/WIRING_AND_SAFETY.md', 'docs/OFFLINE_CAPTURE_HANDOFF.md',
    'docs/physical-connection-pack/README.md', 'docs/physical-connection-pack/connection-guide.html',
    'docs/physical-connection-pack/all-30-connection-matrix.csv',
    'docs/physical-connection-pack/sensor-only-reference.svg',
)
CONTRACT_FILES = ('telemetry-v2.schema.json', 'tests/test_telemetry_v2_contract.py',
                  'examples/telemetry-v2.synthetic-valid.json', 'examples/telemetry-v2.synthetic-partial.json')
SOURCE_FILES = tuple('phase-01-hardware/' + name for name in HARDWARE_FILES) + tuple(
    'enterprise-architecture/contracts/' + name for name in CONTRACT_FILES)
MAX_FILE = 512 * 1024
MAX_TOTAL = 2 * 1024 * 1024
START = """# EDGEOPS hardware arrival pack

Preparation only. The owner reports the same 30 selected products ordered; receipt,
inspection, calibration, connection and production acceptance remain unverified.
No substitutions or additional hardware are authorized by this pack.

1. Keep power disconnected. Open receipt-worksheet.csv and record the actual
   received model, board revision, label/photo references and unresolved issues.
   Blank fields mean unverified. P26-P29 keep their optional installation roles;
   P30 remains a cold spare. All 30 items are retained, not all are wired together.
2. Read phase-01-hardware/docs/physical-connection-pack/README.md and its printable
   connection-guide.html. Sensor wiring is conditional on actual board checks.
   Motor-power wiring and control remain pending exact ordered-part review.
3. Read phase-01-hardware/docs/OFFLINE_CAPTURE_HANDOFF.md. This contains the software
   commands and exit-code meanings. Python 3.12+ is needed for the complete suite.
   The included example is synthetic and opens no hardware port.
4. Firmware source and PlatformIO configuration are included for the existing
   ESP32 target. Dependency installation, compilation and upload are separate
   steps; this download does not establish a successful build or exact-board fit.
   See phase-01-hardware/docs/FIRMWARE_BUILD.md for compile-only instructions.
5. To run offline software checks after installing test dependencies, use the
   commands in the handoff guide from phase-01-hardware. No hardware is needed.

The receipt worksheet is an offline working copy. Editing it does not update the
dashboard, verify purchases, enroll devices or authorize equipment. Capture files
and credentials from your computer are never included in this export.

manifest.json lists file sizes and SHA-256 hashes for corruption checks. It is
not a signature, trusted release, proof of origin or physical acceptance. Verify
sources against the reviewed repository before use. All physical readiness flags
remain false. Do not bypass the dashboard's synthetic-only ingestion boundary.
"""


def build_pack(root):
    root = Path(root)
    plan = read_plan(root)
    project = root.parent.resolve()
    files = {}
    try:
        for name in SOURCE_FILES:
            path = project / name
            # Refuse linked files/directories and paths escaping the selected project.
            if not path.resolve().is_relative_to(project): raise ValueError('Linked source')
            for part in (path, *path.parents):
                if part == project: break
                if part.is_symlink() or getattr(part, 'is_junction', lambda: False)(): raise ValueError('Linked source')
            if not path.is_file() or path.stat().st_size > MAX_FILE: raise ValueError('Unavailable source')
            with path.open('rb') as stream: data = stream.read(MAX_FILE + 1)
            if len(data) > MAX_FILE: raise ValueError('Oversized source')
            files[name] = data
        matrix = files['phase-01-hardware/docs/physical-connection-pack/all-30-connection-matrix.csv']
        if hashlib.sha256(matrix.replace(b'\r\n', b'\n')).hexdigest() != plan['source_csv_sha256']:
            raise ValueError('Changed hardware selection')
        rows = list(csv.DictReader(io.StringIO(matrix.decode('utf-8-sig'))))
        if [row['ID'] for row in rows] != [f'P{i:02}' for i in range(1, 31)]: raise ValueError('Changed scope')
        if [row['GitHub part/family'] for row in rows] != [row['selected_family'] for row in plan['rows']]:
            raise ValueError('Changed families')
        worksheet = io.StringIO(newline='')
        writer = csv.writer(worksheet)
        writer.writerow(['Product ID', 'BOM ID', 'Selected family', 'Planned quantity', 'Bench role',
                         'Actual received model / board revision', 'Received date', 'Label / photo reference',
                         'Inspection notes / unresolved issue', 'Record status'])
        for index, row in enumerate(rows, 1):
            writer.writerow([row['ID'], f'BOM-{index:02}', row['GitHub part/family'], row['Planned quantity'],
                             row['Bench role'], '', '', '', '', 'awaiting-delivery-unverified'])
        files['receipt-worksheet.csv'] = worksheet.getvalue().encode('utf-8-sig')
        files['START-HERE.md'] = START.encode()
        files['physical-plan.json'] = (json.dumps(plan, indent=2) + '\n').encode()
        if sum(map(len, files.values())) > MAX_TOTAL: raise ValueError('Oversized pack')
        manifest = {'format': 'edgeops-arrival-pack-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
                    'ordered_count_user_reported': 30, 'received_count_verified': 0,
                    'order_verified': False, 'hardware_connected': False, 'calibration_verified': False,
                    'production_ready': False, 'substitution_allowed': False, 'additional_hardware_allowed': False,
                    'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in files.items()}}
        files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items(): archive.writestr(name, data)
        return output.getvalue()
    except (OSError, ValueError, KeyError, TypeError, csv.Error):
        raise HTTPException(503, 'Arrival pack is unavailable; refresh or restore the reviewed preparation sources')
