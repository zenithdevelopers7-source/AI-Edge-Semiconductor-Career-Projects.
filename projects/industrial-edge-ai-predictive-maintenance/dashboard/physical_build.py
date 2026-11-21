"""Read-only bench preparation for the user's existing fixed 30-product scope."""
import hashlib
import json
from pathlib import Path

from fastapi import HTTPException,Request
from fastapi.responses import FileResponse, Response
from maintenance_requests import require_role,READ_ROLES


def read_plan(root):
    path=root/'physical-build-plan.json'
    try:
        raw=path.read_bytes()
        data=json.loads(raw)
        expected=[f'BOM-{i:02}' for i in range(1,31)]
        if (len(data['rows'])!=30 or [row['id'] for row in data['rows']]!=expected
                or data['version']!='fixed-30-physical-build-v1' or data['ordered_count_user_reported']!=30
                or data['production_ready'] is not False
                or data['additional_hardware_allowed'] is not False or data['substitution_allowed'] is not False
                or data['hardware_connected'] is not False or data['order_verified'] is not False
                or data['pins']!={'SDA':21,'SCL':22,'temperature_data':4}):
            raise ValueError('Unsupported physical plan')
        if any(not isinstance(row.get(key),str) or len(row[key])>2000 for row in data['rows'] for key in ('selected_family','quantity_basis','role','connection','pending')):raise ValueError('Invalid plan entry')
        data['plan_sha256']=hashlib.sha256(raw).hexdigest()
        return data
    except (OSError,ValueError,KeyError,TypeError):
        raise HTTPException(503,'Physical preparation plan is unavailable; no connection instructions returned')


def install_routes(app,require_user,root):
    root=Path(root)
    @app.get('/api/hardware/physical-plan/arrival-pack')
    def arrival_pack(request:Request):
        require_role(require_user(request),READ_ROLES)
        from hardware_handover import build_pack
        return Response(build_pack(root), media_type='application/zip', headers={
            'Content-Disposition':'attachment; filename="edgeops-hardware-arrival-pack.zip"',
            'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})

    @app.get('/api/hardware/physical-plan')
    def physical_plan(request:Request):
        require_role(require_user(request),READ_ROLES)
        data=read_plan(root)
        return data

    @app.get('/api/hardware/physical-plan/sensor-map')
    def sensor_map(request:Request):
        require_role(require_user(request),READ_ROLES)
        data=read_plan(root)
        path=root/'physical-sensor-map.svg'
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=data.get('sensor_map_sha256'):
            raise HTTPException(503,'Sensor reference unavailable or changed')
        return FileResponse(path,media_type='image/svg+xml')
