"""Fixed-parts scope and truthful physical state; no bench operation is performed."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from fastapi import HTTPException
import physical_build
import hardware_handover
import test_acquisition_registry as fixtures

ROOT=Path(__file__).resolve().parents[1]


class PhysicalPlanTests(unittest.TestCase):
    def test_same_30_parts_and_firmware_map_match_source(self):
        data=physical_build.read_plan(ROOT)
        source=ROOT/'../phase-01-hardware/docs/physical-connection-pack/all-30-connection-matrix.csv'
        with source.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
        self.assertEqual([row['selected_family'] for row in data['rows']],[row['GitHub part/family'] for row in rows])
        self.assertEqual(data['source_csv_sha256'],hashlib.sha256(source.read_bytes().replace(b'\r\n',b'\n')).hexdigest())
        self.assertEqual(data['sensor_map_sha256'],hashlib.sha256((ROOT/'physical-sensor-map.svg').read_bytes()).hexdigest())
        self.assertFalse(data['additional_hardware_allowed']);self.assertFalse(data['substitution_allowed'])
        self.assertFalse(data['order_verified']);self.assertFalse(data['hardware_connected'])

    def test_invalid_or_expanded_plan_is_not_presented_as_connection_guidance(self):
        with tempfile.TemporaryDirectory(prefix='edgeops-build-plan-') as temp:
            path=Path(temp)
            for change in ('extra','connected','replacement'):
                data=physical_build.read_plan(ROOT)
                if change=='extra':data['rows'].append(data['rows'][0])
                if change=='connected':data['hardware_connected']=True
                if change=='replacement':data['substitution_allowed']=True
                (path/'physical-build-plan.json').write_text(json.dumps(data),encoding='utf-8')
                with self.assertRaises(HTTPException) as context:physical_build.read_plan(path)
                self.assertEqual(context.exception.status_code,503)


class PhysicalPlanApiTests(unittest.TestCase):
    login=fixtures.AcquisitionRegistryApiTests.login
    post=fixtures.AcquisitionRegistryApiTests.post
    def setUp(self):fixtures.AcquisitionRegistryApiTests.setUp(self)

    def test_arrival_pack_is_authenticated_fixed_scope_and_contains_no_runtime_data(self):
        for role in ('admin','operator','auditor'):
            self.login(role)
            response=self.http.get('/api/hardware/physical-plan/arrival-pack')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'no-store')
            self.assertIn('edgeops-hardware-arrival-pack.zip',response.headers['content-disposition'])
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                expected=set(hardware_handover.SOURCE_FILES)|{'receipt-worksheet.csv','physical-plan.json','START-HERE.md','manifest.json'}
                self.assertEqual(set(archive.namelist()),expected)
                manifest=json.loads(archive.read('manifest.json'))
                self.assertFalse(manifest['hardware_connected']);self.assertFalse(manifest['production_ready'])
                self.assertEqual(manifest['received_count_verified'],0)
                for name,entry in manifest['files'].items():
                    content=archive.read(name)
                    self.assertEqual(entry,{'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
                rows=list(csv.DictReader(io.StringIO(archive.read('receipt-worksheet.csv').decode('utf-8-sig'))))
                self.assertEqual([row['Product ID'] for row in rows],[f'P{i:02}' for i in range(1,31)])
                self.assertTrue(all(row['Actual received model / board revision']=='' and row['Record status']=='awaiting-delivery-unverified' for row in rows))
                self.assertEqual(archive.read('phase-01-hardware/scripts/capture_serial.py'),(ROOT/'../phase-01-hardware/scripts/capture_serial.py').read_bytes())
        self.http.cookies.clear()
        self.assertEqual(self.http.get('/api/hardware/physical-plan/arrival-pack').status_code,401)

    def test_pack_failure_never_returns_a_partial_archive(self):
        with patch.object(hardware_handover,'SOURCE_FILES',('phase-01-hardware/nonexistent-source',)):
            response=self.http.get('/api/hardware/physical-plan/arrival-pack')
            self.assertEqual(response.status_code,503)
            self.assertIn('application/json',response.headers['content-type'])

    def test_order_report_is_separate_from_physical_verification_and_plan_is_read_only(self):
        for role in ('admin','operator','auditor'):
            self.login(role)
            catalog=self.http.get('/api/hardware').json()
            self.assertEqual(catalog['ordered_count_user_reported'],30)
            self.assertTrue(all(row['lifecycle']=='ordered-user-reported' and not row['connected'] and not row['purchase_verified'] for row in catalog['devices']))
            plan=self.http.get('/api/hardware/physical-plan').json()
            self.assertEqual(len(plan['rows']),30);self.assertFalse(plan['production_ready'])
            self.assertEqual(self.http.get('/api/hardware/physical-plan/sensor-map').status_code,200)
            self.assertEqual(self.post('/api/hardware/physical-plan',{'hardware_connected':True}).status_code,405)
        self.http.cookies.clear()
        self.assertEqual(self.http.get('/api/hardware/physical-plan').status_code,401)
        self.assertEqual(self.http.get('/api/hardware/physical-plan/sensor-map').status_code,401)


class ArrivalPackIntegrityTests(unittest.TestCase):
    def test_changed_matrix_and_source_outside_project_are_refused(self):
        with patch.object(hardware_handover,'read_plan',return_value=dict(physical_build.read_plan(ROOT),source_csv_sha256='0'*64)):
            with self.assertRaises(HTTPException) as result:hardware_handover.build_pack(ROOT)
            self.assertEqual(result.exception.status_code,503)
        with patch.object(hardware_handover,'SOURCE_FILES',('../outside.txt',)):
            with self.assertRaises(HTTPException) as result:hardware_handover.build_pack(ROOT)
            self.assertEqual(result.exception.status_code,503)
