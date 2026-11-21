"""Private local backup, verification and restore-to-new-directory tools.

No server import, bootstrap, live overwrite, archive extraction or network calls.
Backups contain identity data. Protect the directory like the original database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import tempfile
from datetime import datetime, timezone

FORMAT = 'edgeops-local-backup-v1'
MAX_FILES = 10000
MAX_BYTES = 2 * 1024 ** 3
ARTIFACT_KINDS = {'datasets', 'models', 'runs', 'comparison-datasets', 'comparisons'}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def regular(path):
    if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
        raise ValueError('Linked backup paths are not supported')
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Expected a regular backup file')


def connect_readonly(path):
    regular(path)
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True, timeout=10)
    try:
        db.execute('PRAGMA trusted_schema=OFF')
        return db
    except BaseException:
        db.close()
        raise


def database_counts(path, kind):
    db = connect_readonly(path)
    try:
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('Database integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Database contains broken references')
        names = [row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        required = {'users', 'sessions', 'audit'} if kind == 'dashboard' else {'delivery_spool'} if kind == 'delivery' else {'synthetic_telemetry'}
        if not required.issubset(names) or len(names) > 200:
            raise ValueError('Unexpected database schema')
        return {name: db.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
                for name in sorted(names)}
    finally:
        db.close()


def snapshot(source, target):
    source_db = connect_readonly(source)
    target_db = sqlite3.connect(target)
    try:
        source_db.backup(target_db)
        # A standalone snapshot must not depend on WAL sidecar files.
        target_db.execute("PRAGMA journal_mode=DELETE")
        target_db.commit()
    finally:
        target_db.close()
        source_db.close()
    os.chmod(target, 0o600)


def new_stage(destination):
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination must be a new directory; existing data is never overwritten')
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination, Path(tempfile.mkdtemp(prefix='.edgeops-pending-', dir=destination.parent))


def publish(stage, destination):
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination appeared during operation; refusing overwrite')
    stage.rename(destination)


def create_backup(database, output, telemetry=None, artifacts=None, delivery_spool=None):
    database = Path(database).absolute()
    database_counts(database, 'dashboard')
    destination, stage = new_stage(output)
    try:
        snapshot(database, stage / 'dashboard.sqlite3')
        roles = {'dashboard.sqlite3': 'dashboard'}
        if telemetry is not None:
            telemetry = Path(telemetry).absolute()
            database_counts(telemetry, 'telemetry')
            snapshot(telemetry, stage / 'synthetic-telemetry.sqlite3')
            roles['synthetic-telemetry.sqlite3'] = 'telemetry'
        if delivery_spool is not None:
            delivery_spool = Path(delivery_spool).absolute()
            database_counts(delivery_spool, 'delivery')
            snapshot(delivery_spool, stage / 'delivery-spool.sqlite3')
            roles['delivery-spool.sqlite3'] = 'delivery'
        if artifacts is not None:
            root = Path(artifacts).absolute()
            if not root.is_dir() or root.is_symlink() or getattr(root, 'is_junction', lambda: False)():
                raise ValueError('Artifacts must be an existing ordinary directory')
            if destination.resolve().is_relative_to(root.resolve()):
                raise ValueError('Backup destination cannot be inside its artifact source')
            for source in root.rglob('*'):
                if source.is_symlink() or getattr(source, 'is_junction', lambda: False)():
                    raise ValueError('Linked artifacts are not supported')
                if source.is_dir():
                    continue
                regular(source)
                rel = source.relative_to(root)
                if (len(rel.parts) != 2 or rel.parts[0] not in ARTIFACT_KINDS
                        or not re.fullmatch(r'[0-9a-f]{64}\.json', rel.name)):
                    raise ValueError('Artifact source contains unsupported files')
                target = stage / 'artifacts' / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                os.chmod(target, 0o600)
                roles[target.relative_to(stage).as_posix()] = 'artifact'
                if len(roles) > MAX_FILES or sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()) > MAX_BYTES:
                    raise ValueError('Backup exceeds local size or file limits')
        entries = []
        for name, role in sorted(roles.items()):
            path = stage / name
            item = {'path': name, 'role': role, 'bytes': path.stat().st_size, 'sha256': digest(path)}
            if role != 'artifact':
                item['table_counts'] = database_counts(path, role)
            entries.append(item)
        manifest = {'format': FORMAT, 'created_at': datetime.now(timezone.utc).isoformat(),
                    'consistency': 'per-store-snapshots; stop writers for coordinated recovery point',
                    'contains_private_identity_data': True, 'files': entries,
                    'production_ready': False}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        os.chmod(stage / 'manifest.json', 0o600)
        verify_backup(stage)
        publish(stage, destination)
        return {'verified': True, 'file_count': len(entries), 'production_ready': False}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_backup(directory):
    root = Path(directory).absolute()
    if root.is_symlink() or getattr(root, 'is_junction', lambda: False)():
        raise ValueError('Linked backup directories are not supported')
    manifest_path = root / 'manifest.json'
    regular(manifest_path)
    if manifest_path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Manifest too large')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    entries = manifest.get('files')
    if manifest.get('format') != FORMAT or not isinstance(entries, list) or not 1 <= len(entries) <= MAX_FILES:
        raise ValueError('Unsupported backup manifest')
    expected, total = {'manifest.json'}, 0
    for item in entries:
        name = item['path']
        if not isinstance(name, str) or '\\' in name or ':' in name:
            raise ValueError('Unsafe backup path')
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or rel.as_posix() != name or name.casefold() in expected:
            raise ValueError('Unsafe or duplicate backup path')
        role = item['role']
        if role == 'dashboard' and name == 'dashboard.sqlite3':
            pass
        elif role == 'telemetry' and name == 'synthetic-telemetry.sqlite3':
            pass
        elif role == 'delivery' and name == 'delivery-spool.sqlite3':
            pass
        elif (role == 'artifact' and len(rel.parts) == 3 and rel.parts[0] == 'artifacts'
              and rel.parts[1] in ARTIFACT_KINDS and re.fullmatch(r'[0-9a-f]{64}\.json', rel.name)):
            pass
        else:
            raise ValueError('Unsupported file role or location')
        expected.add(name.casefold())
        path = root.joinpath(*rel.parts)
        for parent in path.parents:
            if parent == root:
                break
            if parent.is_symlink() or getattr(parent, 'is_junction', lambda: False)():
                raise ValueError('Linked backup paths are not supported')
        regular(path)
        size = item['bytes']
        if type(size) is not int or size < 0:
            raise ValueError('Invalid backup size')
        total += size
        if total > MAX_BYTES or path.stat().st_size != size or digest(path) != item['sha256']:
            raise ValueError('Backup integrity mismatch')
        if role == 'artifact' and item['sha256'] != rel.stem:
            raise ValueError('Artifact content address mismatch')
        if role != 'artifact' and database_counts(path, role) != item['table_counts']:
            raise ValueError('Database record reconciliation failed')
    if 'dashboard.sqlite3' not in expected:
        raise ValueError('Dashboard database is missing')
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
            raise ValueError('Linked backup paths are not supported')
        if path.is_file():
            regular(path)
            actual.add(path.relative_to(root).as_posix().casefold())
    if actual != expected:
        raise ValueError('Unlisted or missing backup files')
    return manifest


def restore_backup(directory, output):
    manifest = verify_backup(directory)
    root = Path(directory).absolute()
    if Path(output).resolve().is_relative_to(root.resolve()):
        raise ValueError('Restore destination cannot be inside its backup source')
    destination, stage = new_stage(output)
    try:
        for item in manifest['files']:
            target = stage / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / item['path'], target)
            os.chmod(target, 0o600)
            if digest(target) != item['sha256']:
                raise ValueError('Backup changed during restoration')
        db = sqlite3.connect(stage / 'dashboard.sqlite3')
        try:
            with db:
                revoked = db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
                db.execute('DELETE FROM sessions')
                db.execute('INSERT INTO audit(time_utc,actor,action,detail) VALUES(?,?,?,?)',
                           (datetime.now(timezone.utc).isoformat(), 'local-recovery-tool',
                            'recovery_restore', 'Restored verified snapshot; existing browser sessions revoked'))
        finally:
            db.close()
        counts = database_counts(stage / 'dashboard.sqlite3', 'dashboard')
        original = next(e['table_counts'] for e in manifest['files'] if e['role'] == 'dashboard')
        for table, count in original.items():
            wanted = 0 if table == 'sessions' else count + 1 if table == 'audit' else count
            if counts[table] != wanted:
                raise ValueError('Restored record reconciliation failed')
        report = {'format': 'edgeops-restore-report-v1', 'verified': True,
                  'restored_at': datetime.now(timezone.utc).isoformat(),
                  'sessions_revoked': revoked, 'table_counts': counts,
                  'production_ready': False, 'source_manifest_sha256': digest(root / 'manifest.json')}
        (stage / 'restore-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        os.chmod(stage / 'restore-report.json', 0o600)
        publish(stage, destination)
        return report
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    backup = commands.add_parser('backup')
    backup.add_argument('--database', required=True)
    backup.add_argument('--telemetry')
    backup.add_argument('--artifacts')
    backup.add_argument('--delivery-spool')
    backup.add_argument('--output', required=True)
    verify = commands.add_parser('verify')
    verify.add_argument('directory')
    restore = commands.add_parser('restore')
    restore.add_argument('directory')
    restore.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'backup':
            result = create_backup(args.database, args.output, args.telemetry, args.artifacts, args.delivery_spool)
        elif args.command == 'verify':
            manifest = verify_backup(args.directory)
            result = {'verified': True, 'file_count': len(manifest['files']), 'production_ready': False}
        else:
            result = restore_backup(args.directory, args.output)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError) as error:
        parser.exit(1, 'Recovery operation failed: ' + str(error) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
