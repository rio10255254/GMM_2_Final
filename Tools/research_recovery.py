"""Build and verify a reviewed research recovery collection without deleting sources.

The experiment interpretation is supplied in a separately reviewed JSON document.
File classification is an inventory aid, never a scientific verdict or deletion grant.
All output must be outside the original project. No command in this tool deletes,
moves, trains, changes a checkpoint, or updates a Git branch.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import sys
import time
import zipfile

CODE = {'.py', '.m', '.ps1', '.cmd', '.bat', '.sh', '.c', '.cpp', '.h', '.hpp',
        '.cu', '.cuh', '.toml', '.yaml', '.yml', '.ini', '.cfg', '.css', '.js'}
TEXT = {'.md', '.rst', '.html', '.tex', '.bib', '.txt', '.log'}
NUMERIC = {'.csv', '.tsv', '.json', '.jsonl', '.xlsx', '.xls', '.npz', '.npy', '.mat'}
IMAGE = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.svg', '.pdf'}
SKIP = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
        '.venv', 'venv', 'node_modules', 'site-packages', 'dlls', '.claude',
        '.vscode', '.history', 'portable_runtime', '_portable_env_sim_20260318',
        '_codex_store_backups', 'trash_archive', 'project_archive'}
BULK = {'arrays', 'reconstructions', 'reconstruction', 'reconstruct_progress',
        'payload', 'payload_v2', 'package', 'package_v2', 'generated_training_data',
        'training_datasets', 'training_data', 'clear', 'blur', 'geometry',
        'latent', 'latents', 'sources', 'targets', 'inputs', 'raw_inputs'}


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_relative(value: str) -> Path:
    value = value.replace('\\', '/')
    p = PurePosixPath(value)
    if not value or not p.parts or p.is_absolute() or '..' in p.parts or ':' in value:
        raise ValueError(f'Unsafe project-relative path: {value!r}')
    return Path(*p.parts)


def external_output(root: Path, output: Path) -> Path:
    root = root.resolve(strict=True)
    output = output.resolve()
    if output == root or root in output.parents:
        raise ValueError('Recovery output must be outside the original project')
    return output


def experiment_roots(root: Path) -> list[str]:
    result = []
    for rel in ['Experiments', 'Thesis_MOSR_Evidence/LabSystem_MOSR/Experiments']:
        base = root / rel
        if base.exists():
            result.extend((p.relative_to(root).as_posix()) for p in sorted(base.iterdir())
                          if p.is_dir() and not p.name.startswith('.') and p.name != 'reports')
    for base in sorted((root / 'Traing_Progress').glob('organized*')):
        if base.name < 'organized_20260313':
            result.append(base.relative_to(root).as_posix())
        else:
            result.extend(p.relative_to(root).as_posix() for p in sorted(base.iterdir())
                          if p.is_dir() and (p.name.startswith('round') or p.name in
                             {'branch_e', 'branch_e_followup', 'diagnostics',
                              'pairwise_delta_probe', 'estimator_formula_probe', 'tta_experiment'}))
    return result


def scope_for(path: str, scopes: list[str]) -> str:
    for scope in scopes:
        if path == scope or path.startswith(scope + '/'):
            return scope
    return path.split('/')[0]


def classify(path: str, size: int) -> str:
    p = PurePosixPath(path)
    parts = [s.lower() for s in p.parts]
    if any(s in SKIP for s in parts):
        return 'excluded_cache_or_environment'
    suffix = p.suffix.lower()
    name = p.name.lower()
    if suffix in {'.pth', '.pt', '.ckpt', '.onnx'} or name.endswith('.pth.tar'):
        return 'model_candidate'
    if suffix in CODE or name in {'requirements.txt', 'license', 'copying', '.gitignore', '.gitattributes'}:
        return 'code_and_settings'
    if suffix in TEXT:
        if suffix == '.txt' and any(s in BULK for s in parts) and not any(
                word in name for word in ['manifest', 'readme', 'gmf', 'score', 'log', 'summary', 'requirements']):
            return 'per_example_metadata'
        return 'document_or_log'
    if suffix in NUMERIC:
        if suffix in {'.json', '.jsonl'} and any(word in name for word in [
                'manifest', 'audit', 'config', 'plan', 'summary', 'status', 'state',
                'lock', 'complete', 'verified', 'verification', 'history', 'metrics',
                'receipt', 'decision', 'protocol', 'reference', 'calibration', 'progress', 'recipe']):
            return 'results_and_provenance'
        if suffix in {'.csv', '.tsv', '.xlsx', '.xls'}:
            return 'results_and_provenance'
        if any(s in BULK for s in parts):
            return 'generated_payload_or_input'
        if suffix in {'.npz', '.npy', '.mat'}:
            return 'numeric_array_candidate'
        return 'results_and_provenance'
    if suffix in IMAGE:
        return 'image_candidate'
    if suffix in {'.zip', '.7z', '.gz', '.tar', '.rar'}:
        return 'existing_package'
    return 'other'


def catalog(root: Path, inventory: Path, output: Path):
    output = external_output(root, output)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    scopes = sorted(experiment_roots(root), key=len, reverse=True)
    db = sqlite3.connect(output)
    db.execute('CREATE TABLE files(path TEXT PRIMARY KEY, bytes INTEGER, extension TEXT, scope TEXT, role TEXT)')
    rows = []
    count = 0
    with gzip.open(inventory, 'rt', encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream):
            if row['kind'] != 'file':
                continue
            path = row['relative_path'].replace('\\', '/')
            size = int(row['size_bytes'])
            role = classify(path, size)
            if role in {'excluded_cache_or_environment', 'other'}:
                continue
            rows.append((path, size, row['extension'], scope_for(path, scopes), role))
            count += 1
            if len(rows) >= 10000:
                db.executemany('INSERT INTO files VALUES (?,?,?,?,?)', rows)
                rows.clear()
    db.executemany('INSERT INTO files VALUES (?,?,?,?,?)', rows)
    db.execute('CREATE INDEX role_index ON files(role)')
    db.execute('CREATE INDEX scope_index ON files(scope)')
    db.commit()
    summary = [dict(zip(['role', 'files', 'bytes'], row)) for row in db.execute(
        'SELECT role,count(*),sum(bytes) FROM files GROUP BY role')]
    write_json(output.with_suffix('.json'), {'scopes': sorted(scopes), 'files': count, 'summary': summary})
    print(json.dumps({'catalog': str(output), 'files': count, 'summary': summary}, indent=2))
    db.close()


def verify_files(root: Path, manifest: Path, report: Path):
    if report.exists():
        raise FileExistsError('Verification reports must use a new path')
    items = read_json(manifest)['files']
    failures = []
    for item in items:
        path = root / safe_relative(item['path'])
        if not path.is_file():
            failures.append({'path': item['path'], 'reason': 'missing'})
        elif path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            failures.append({'path': item['path'], 'reason': 'changed'})
    value = {'status': 'PASS' if not failures else 'FAIL', 'files': len(items), 'failures': failures}
    write_json(report, value)
    print(json.dumps(value, ensure_ascii=False))
    return 0 if not failures else 1


def restore_zip(archive: Path, destination: Path):
    """Restore only into an empty directory; validate all members before any write."""
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError('Restore destination must be new or empty')
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            safe_relative(member.filename.rstrip('/'))
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Symlinks are not accepted in recovery ZIPs')
        if z.testzip() is not None:
            raise ValueError('Corrupt recovery ZIP')
        destination.mkdir(parents=True, exist_ok=True)
        for member in z.infolist():
            target = destination / safe_relative(member.filename.rstrip('/'))
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(member) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src, dst)


def copy_selected(root: Path, selection: Path, destination: Path):
    destination = external_output(root, destination)
    spec = read_json(selection)
    if not spec.get('reviewed'):
        raise ValueError('Selection needs an explicit reviewed=true receipt')
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError('Export destination must be new or empty')
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in spec['files']:
        rel = safe_relative(item['path'])
        source = root / rel
        if not source.is_file():
            raise FileNotFoundError(source)
        # Hash before and after copying to refuse a changing source.
        before = digest(source)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(target) != before or digest(source) != before:
            raise RuntimeError(f'Source changed during export: {rel}')
        rows.append({'path': rel.as_posix(), 'bytes': target.stat().st_size,
                     'sha256': before, 'reason': item['reason'], 'role': item['role']})
        if len(rows) % 2000 == 0:
            print(f'verified copied files={len(rows):,}', flush=True)
    manifest = {'schema': 1, 'source': str(root), 'files': rows}
    write_json(destination / 'RECOVERY_FILES.json', manifest)
    print(json.dumps({'export': str(destination), 'files': len(rows),
                      'bytes': sum(row['bytes'] for row in rows)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('catalog')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('copy-selected')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    p = sub.add_parser('verify')
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p = sub.add_parser('restore-zip')
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'catalog':
        catalog(args.root, args.inventory, args.output)
    elif args.command == 'copy-selected':
        copy_selected(args.root, args.selection, args.destination)
    elif args.command == 'verify':
        return verify_files(args.root, args.manifest, args.report)
    elif args.command == 'restore-zip':
        restore_zip(args.archive, args.destination)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
