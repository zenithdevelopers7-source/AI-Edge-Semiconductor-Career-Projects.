#!/usr/bin/env python3
"""Offline V1 capture-CSV to candidate-V2 evidence adapter. No serial/network I/O."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

FIELDS=('gateway_utc','device_id','seq','uptime_ms','ax_mps2','ay_mps2','az_mps2','temp_c','bus_v','current_ma','adxl345_valid','ds18b20_valid','ina219_valid','valid')
MAX_INPUT=16*1024*1024
MAX_ROWS=10000
ADAPTER='edgeops-v1-csv-to-v2-evidence-v1'
ATTACHMENT_FIELDS={'profile','site_id','asset_id','device_id','v1_device_id','serial_port','board_reference','configuration_ref','source_type','physical_verification','calibration','transport'}


def json_bytes(data):return (json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(data):return hashlib.sha256(data).hexdigest()


def read_file(path,limit):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('Input must be an ordinary file')
    if path.stat().st_size>limit:raise ValueError('Input exceeds local evidence size limit')
    with path.open('rb') as stream:data=stream.read(limit+1)
    if len(data)>limit:raise ValueError('Input exceeds local evidence size limit')
    return data


def attachment(data):
    if not isinstance(data,dict) or set(data)!=ATTACHMENT_FIELDS:raise ValueError('Supply the exact serial attachment field set')
    for key,value in data.items():
        if not isinstance(value,str) or not value.strip() or len(value)>200:raise ValueError('Attachment values must be bounded nonempty strings')
    for key in ('site_id','asset_id','device_id','v1_device_id'):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',data[key]):raise ValueError('Invalid attachment identifier')
    if (data['profile']!='edgeops.serial-attachment.v1' or data['transport']!='usb-serial'
            or data['source_type'] not in ('synthetic','measured','replayed')
            or data['physical_verification']!='unverified' or data['calibration']!='not_verified'):
        raise ValueError('Unsupported attachment provenance or verification claim')
    return data


def utc(text):
    if not isinstance(text,str) or len(text)>40 or 'T' not in text:raise ValueError('invalid-receipt-time')
    try:value=datetime.fromisoformat(text)
    except ValueError:raise ValueError('invalid-receipt-time')
    if value.tzinfo is None or value.utcoffset() is None:raise ValueError('receipt-time-without-timezone')
    return value.astimezone(timezone.utc)


def integer(text):
    if not isinstance(text,str) or not re.fullmatch(r'0|[1-9][0-9]{0,9}',text):raise ValueError('invalid-counter')
    value=int(text)
    if value>4294967295:raise ValueError('counter-out-of-range')
    return value


def number(text):
    if not isinstance(text,str) or len(text)>64:raise ValueError('invalid-number')
    if not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?',text):raise ValueError('invalid-number')
    try:value=float(text)
    except ValueError:raise ValueError('invalid-number')
    if not math.isfinite(value):raise ValueError('nonfinite-number')
    return value


def flag(text):
    if text not in ('True','False'):raise ValueError('invalid-boolean')
    return text=='True'


def convert(row,mapping):
    if set(row)!=set(FIELDS) or any(value is None for value in row.values()):raise ValueError('invalid-csv-row')
    if row['device_id']!=mapping['v1_device_id']:raise ValueError('attachment-device-mismatch')
    seq=integer(row['seq']);uptime=integer(row['uptime_ms']);received=utc(row['gateway_utc'])
    flags={key:flag(row[key]) for key in ('adxl345_valid','ds18b20_valid','ina219_valid','valid')}
    if flags['valid']!=(flags['adxl345_valid'] and flags['ds18b20_valid'] and flags['ina219_valid']):raise ValueError('inconsistent-validity')
    values={key:number(row[key]) for key in ('ax_mps2','ay_mps2','az_mps2','temp_c','bus_v','current_ma')}
    a,t,i=flags['adxl345_valid'],flags['ds18b20_valid'],flags['ina219_valid']
    result={'schema_version':'2.0','event_type':'telemetry.sample','source_type':mapping['source_type'],
            'site_id':mapping['site_id'],'asset_id':mapping['asset_id'],'device_id':mapping['device_id'],
            'boot_id':None,'sequence':seq,'timestamp':{'device_uptime_ms':uptime,'device_time_utc':None,
                'gateway_received_utc':received.isoformat(),'clock_quality':'gateway_receipt_only'},
            'measurements':{'acceleration_x_mps2':values['ax_mps2'] if a else None,
                'acceleration_y_mps2':values['ay_mps2'] if a else None,'acceleration_z_mps2':values['az_mps2'] if a else None,
                'motor_case_temperature_c':values['temp_c'] if t else None,'bus_voltage_v':values['bus_v'] if i else None,
                'current_a':values['current_ma']/1000 if i else None},
            'quality':{'adxl345':'valid' if a else 'invalid','ds18b20':'valid' if t else 'invalid',
                'ina219':'valid' if i else 'invalid','calibration':'not_verified','session_quality':'unavailable'}}
    return result,(seq,uptime,received)


def normalize(raw,mapping):
    source=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
    if source.fieldnames is None or len(source.fieldnames)!=len(FIELDS) or set(source.fieldnames)!=set(FIELDS):raise ValueError('Unsupported or duplicate CSV columns')
    accepted=[];quarantine=[];previous=None;ambiguous=False;gaps=0;count=0
    for row in source:
        index=source.line_num
        count+=1
        if count>MAX_ROWS:raise ValueError('Capture exceeds local row limit')
        if ambiguous:quarantine.append({'csv_line':index,'reason':'unresolved-session-or-clock-discontinuity'});continue
        try:
            record,state=convert(row,mapping)
            if previous and (state[0]<=previous[0] or state[1]<previous[1] or state[2]<previous[2]):
                ambiguous=True;raise ValueError('unresolved-session-or-clock-discontinuity')
            if previous:gaps+=max(0,state[0]-previous[0]-1)
            previous=state;accepted.append(record)
        except ValueError as error:quarantine.append({'csv_line':index,'reason':str(error)})
    return accepted,quarantine,gaps,count


def prepare(input_path,attachment_path,output):
    raw=read_file(input_path,MAX_INPUT);mapping=attachment(json.loads(read_file(attachment_path,8192)))
    destination=Path(output).absolute()
    if destination.exists() or destination.is_symlink():raise ValueError('Output must be a new directory; existing evidence is never overwritten')
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.edgeops-capture-pending-',dir=destination.parent))
    try:
        accepted,quarantine,gaps,count=normalize(raw,mapping)
        files={'source.capture.csv':raw,'attachment.json':json_bytes(mapping),
               'observations.jsonl':b''.join(json_bytes(row) for row in accepted),
               'quarantine.jsonl':b''.join(json_bytes(row) for row in quarantine)}
        for name,data in files.items():(stage/name).write_bytes(data)
        manifest={'format':ADAPTER,'created_at':datetime.now(timezone.utc).isoformat(),
                  'source_type':mapping['source_type'],'source_classification':'operator-declared; not physical authentication',
                  'input_rows':count,'accepted_rows':len(accepted),'quarantined_rows':len(quarantine),
                  'accepted_sequence_gaps':gaps,'requires_review':bool(quarantine) or not accepted,
                  'boot_identity':'unavailable','physical_source_verified':False,'calibration_verified':False,
                  'hardware_connected':False,'ready_for_ingestion':False,'production_ready':False,
                  'files':{name:{'bytes':len(data),'sha256':sha(data)} for name,data in files.items()}}
        (stage/'manifest.json').write_bytes(json_bytes(manifest))
        verify(stage)
        if destination.exists() or destination.is_symlink():raise ValueError('Output destination appeared; refusing overwrite')
        stage.rename(destination)
        return manifest
    finally:
        if stage.exists():
            assert stage.resolve().parent==destination.parent.resolve() and stage.name.startswith('.edgeops-capture-pending-')
            shutil.rmtree(stage)


def verify(directory):
    root=Path(directory)
    if root.is_symlink() or getattr(root,'is_junction',lambda:False)():raise ValueError('Linked evidence folders are not supported')
    manifest=json.loads(read_file(root/'manifest.json',65536))
    if not isinstance(manifest,dict):raise ValueError('Unsupported evidence manifest')
    if manifest.get('boot_identity')!='unavailable' or manifest.get('source_classification')!='operator-declared; not physical authentication':raise ValueError('Unsupported provenance claim')
    utc(manifest.get('created_at'))
    expected={'source.capture.csv','attachment.json','observations.jsonl','quarantine.jsonl'}
    if manifest.get('format')!=ADAPTER or set(manifest.get('files',{}))!=expected:raise ValueError('Unsupported evidence manifest')
    if set(path.name for path in root.iterdir())!=expected|{'manifest.json'}:raise ValueError('Unexpected or missing evidence files')
    for name in expected:
        data=read_file(root/name,32*1024*1024)
        if manifest['files'][name]!={'bytes':len(data),'sha256':sha(data)}:raise ValueError('Evidence file integrity mismatch')
    mapping=attachment(json.loads((root/'attachment.json').read_bytes()))
    records=[json.loads(line) for line in (root/'observations.jsonl').read_bytes().splitlines()]
    rejected=[json.loads(line) for line in (root/'quarantine.jsonl').read_bytes().splitlines()]
    if (len(records)!=manifest['accepted_rows'] or len(rejected)!=manifest['quarantined_rows']
            or len(records)+len(rejected)!=manifest['input_rows'] or manifest['input_rows']>MAX_ROWS
            or manifest['source_type']!=mapping['source_type']):raise ValueError('Evidence reconciliation failed')
    normalized,expected_rejected,gaps,count=normalize((root/'source.capture.csv').read_bytes(),mapping)
    if records!=normalized or rejected!=expected_rejected or manifest['accepted_sequence_gaps']!=gaps or manifest['input_rows']!=count or manifest['requires_review']!=(bool(rejected) or not records):
        raise ValueError('Prepared observations do not match source transformation')
    for key in ('physical_source_verified','calibration_verified','hardware_connected','ready_for_ingestion','production_ready'):
        if manifest.get(key) is not False:raise ValueError('Unsupported verification claim')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    create=commands.add_parser('prepare');create.add_argument('--input',required=True);create.add_argument('--attachment',required=True);create.add_argument('--output',required=True)
    check=commands.add_parser('verify');check.add_argument('directory')
    args=parser.parse_args()
    try:manifest=prepare(args.input,args.attachment,args.output) if args.command=='prepare' else verify(args.directory)
    except (ValueError,OSError,KeyError,TypeError,csv.Error):parser.exit(1,'Evidence preparation failed; check the capture, attachment and output paths. Existing files were not overwritten.\n')
    print(json.dumps({key:manifest[key] for key in ('accepted_rows','quarantined_rows','requires_review','physical_source_verified','ready_for_ingestion')},sort_keys=True))
    return 2 if args.command=='prepare' and manifest['requires_review'] else 0


if __name__=='__main__':raise SystemExit(main())
