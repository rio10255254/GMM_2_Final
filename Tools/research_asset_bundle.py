"""Pack reviewed research sources/results once and restore verified original paths.

The selection is explicit. Identical bytes share one object, but every original
path keeps its own provenance entry. This tool never removes source files.
"""
import argparse
from collections import defaultdict
import concurrent.futures
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
import zipfile

from research_recovery import digest, external_output, safe_relative, write_json


def inspect(row, root):
    relative = safe_relative(row['path']).as_posix()
    source = Path(row.get('source', str(root / relative)))
    before = source.stat()
    checksum = digest(source)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError('Source changed while hashing: ' + relative)
    if row.get('sha256') is not None and row['sha256'] != checksum:
        raise ValueError('Source differs from its reviewed content identity: ' + relative)
    if row.get('bytes') is not None and row['bytes'] != before.st_size:
        raise ValueError('Source differs from its reviewed byte count: ' + relative)
    return {**row, 'path': relative, 'bytes': before.st_size, 'sha256': checksum,
            '_source': str(source), '_mtime_ns': before.st_mtime_ns}


def pack(root, selection, output, part_limit, workers=4):
    output = external_output(root, output)
    if not 0 < part_limit <= 1_850_000_000:
        raise ValueError('Invalid release part size')
    spec = json.loads(selection.read_text(encoding='utf-8-sig'))
    if not spec.get('reviewed'):
        raise ValueError('An explicitly reviewed selection is required')
    if output.exists():
        raise FileExistsError('Use a new bundle directory')
    output.mkdir(parents=True)
    paths = [safe_relative(row['path']).as_posix().casefold() for row in spec['files']]
    if len(paths) != len(set(paths)):
        raise ValueError('Duplicate or case-conflicting destination paths')
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for row in pool.map(lambda row: inspect(row, root), spec['files']):
            rows.append(row)
            if len(rows) % 4000 == 0:
                print('BUNDLE_SOURCES_HASHED', len(rows), len(paths), flush=True)
    unique = {}
    for row in rows:
        if row['bytes'] > part_limit:
            raise ValueError('Single file exceeds bundle limit: ' + row['path'])
        unique.setdefault(row['sha256'], row)
    groups = []; current = []; total = 0; current_collection = None
    for checksum, row in sorted(unique.items(), key=lambda item: (item[1].get('collection', 'general'), item[0])):
        collection = row.get('collection', 'general')
        if not re.fullmatch('[a-z0-9-]{1,64}', collection):
            raise ValueError('Invalid reviewed collection name')
        if current and (collection != current_collection or total + row['bytes'] + 256 > part_limit):
            groups.append((current_collection, current)); current = []; total = 0
        current_collection = collection
        current.append(row); total += row['bytes'] + 256
    if current:
        groups.append((current_collection, current))
    parts = []; locations = {}
    for index, (collection, group) in enumerate(groups, 1):
        name = f'research-{collection}-{index:03d}.zip'
        destination = output / name
        with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as archive:
            for row in group:
                checksum = row['sha256']; source = Path(row['_source'])
                before = source.stat()
                if before.st_size != row['bytes'] or before.st_mtime_ns != row['_mtime_ns']:
                    raise RuntimeError('Source changed before packing: ' + row['path'])
                calculated = hashlib.sha256()
                with source.open('rb') as stream, archive.open('objects/' + checksum, 'w', force_zip64=True) as target:
                    while block := stream.read(4 * 1024**2):
                        calculated.update(block); target.write(block)
                after = source.stat()
                if calculated.hexdigest() != checksum or (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
                    raise RuntimeError('Source changed during packing: ' + row['path'])
                locations[checksum] = name
        if destination.stat().st_size >= 2 * 1024**3:
            raise ValueError('Compressed release asset exceeds GitHub limit')
        parts.append({'name': name, 'bytes': destination.stat().st_size,
                      'sha256': digest(destination), 'objects': len(group), 'collection': collection})
        print('BUNDLE_PART_VERIFIED', name, destination.stat().st_size, flush=True)
    public_rows = []
    for row in rows:
        value = {key: value for key, value in row.items() if not key.startswith('_') and key != 'source'}
        value['asset'] = locations[row['sha256']]
        if 'source' in row:
            value['historical_source'] = row['source']
        public_rows.append(value)
    manifest = {'schema': 1, 'state': 'complete', 'files': public_rows, 'assets': parts,
                'paths': len(rows), 'unique_objects': len(unique),
                'original_bytes': sum(row['bytes'] for row in rows),
                'unique_bytes': sum(row['bytes'] for row in unique.values()),
                'packed_bytes': sum(part['bytes'] for part in parts),
                'full_historical_training_repeated': False, 'deletion_authorized_by_this_manifest': False}
    with gzip.open(output / 'RESEARCH_ASSETS.json.gz', 'wt', encoding='utf-8') as stream:
        json.dump(manifest, stream, ensure_ascii=False, separators=(',', ':'))
    write_json(output / 'BUNDLE_SUMMARY.json', {k: v for k, v in manifest.items() if k != 'files'})
    return manifest


def restore(manifest_path, assets, destination, prefixes=(), keep_identical_existing=False):
    existing_content = destination.exists() and any(destination.iterdir())
    if existing_content and not keep_identical_existing:
        raise FileExistsError('Restore destination must be new or empty')
    with gzip.open(manifest_path, 'rt', encoding='utf-8') as stream:
        manifest = json.load(stream)
    receipt = destination / ('RESTORE_' + digest(manifest_path)[:12] + '_VERIFIED.json')
    if receipt.exists():
        if not keep_identical_existing:
            raise FileExistsError('Restore receipt already exists')
        # A second requested scope or an interrupted/repeated recovery still
        # preflights every selected existing file. Retain the earlier receipt
        # instead of blocking a valid continuation or replacing its evidence.
        receipt = destination / ('RESTORE_' + digest(manifest_path)[:12] +
                                 '_RECHECK_' + uuid.uuid4().hex[:16] + '_VERIFIED.json')
    if manifest.get('state') != 'complete':
        raise ValueError('Incomplete research bundle')
    prefix_roots = [safe_relative(value) for value in prefixes]
    paths = set(); groups = defaultdict(list)
    for row in manifest['files']:
        relative = safe_relative(row['path'])
        normalized = relative.as_posix().casefold()
        if normalized in paths or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('Duplicate path or invalid object identity')
        paths.add(normalized)
        if not prefix_roots or any(relative.is_relative_to(prefix) for prefix in prefix_roots):
            groups[row['asset']].append(row)
    specifications = {row['name']: row for row in manifest['assets']}
    if not groups or len(specifications) != len(manifest['assets']):
        raise ValueError('No selected files or duplicate asset names')
    for name in groups:
        if Path(name).name != name or name not in specifications:
            raise ValueError('Invalid asset name')
        source = assets / name; expected = specifications[name]
        if source.stat().st_size != expected['bytes'] or digest(source) != expected['sha256']:
            raise ValueError('Research asset changed: ' + name)
    resolved_destination = destination.resolve()
    reused = set()
    checked_parents = set()
    # Existing clone metadata can be reused only if every byte is identical.
    # Preflight every path before creating any additional output file.
    for rows in groups.values():
        for row in rows:
            target = destination / safe_relative(row['path'])
            # A new empty output has no pre-existing child redirects. For a
            # clone, resolve each shared parent once, then inspect any existing
            # file separately. Never resolve millions of nonexistent file paths.
            if existing_content and target.parent not in checked_parents:
                if not target.parent.resolve().is_relative_to(resolved_destination):
                    raise ValueError('Existing parent redirects outside the restore directory')
                checked_parents.add(target.parent)
            if existing_content and (target.exists() or target.is_symlink()):
                if not target.resolve().is_relative_to(resolved_destination):
                    raise ValueError('Existing path redirects outside the restore directory')
                if not keep_identical_existing or not target.is_file() or target.stat().st_size != row['bytes'] or digest(target) != row['sha256']:
                    raise FileExistsError('Existing restore file differs: ' + row['path'])
                reused.add(row['path'])
    destination.mkdir(parents=True, exist_ok=True)
    checked = 0; total = 0
    created_parents = set()
    for name, rows in groups.items():
        with zipfile.ZipFile(assets / name) as archive:
            for row in rows:
                if row['path'] in reused:
                    checked += 1; total += row['bytes']
                    continue
                target = destination / safe_relative(row['path'])
                if target.parent not in created_parents:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    created_parents.add(target.parent)
                calculated = hashlib.sha256(); size = 0
                with archive.open('objects/' + row['sha256']) as stream, target.open('xb') as output:
                    while block := stream.read(4 * 1024**2):
                        output.write(block); calculated.update(block); size += len(block)
                if size != row['bytes'] or calculated.hexdigest() != row['sha256'] or digest(target) != row['sha256']:
                    raise ValueError('Restored file differs: ' + row['path'])
                checked += 1; total += size
        print('BUNDLE_RESTORED', name, checked, flush=True)
    report = {'status': 'PASS', 'files_restored_and_verified': checked,
              'bytes_restored': total, 'selected_prefixes': list(prefixes),
              'identical_existing_files_reused': len(reused)}
    write_json(receipt, report)
    return report


def verify_bundle(manifest_path, assets, report):
    if report.exists():
        raise FileExistsError('Verification receipt already exists')
    with gzip.open(manifest_path, 'rt', encoding='utf-8') as stream:
        manifest = json.load(stream)
    if manifest.get('state') != 'complete':
        raise ValueError('Incomplete bundle')
    expected = defaultdict(dict); paths = set()
    for row in manifest['files']:
        path = safe_relative(row['path']).as_posix().casefold()
        if path in paths or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('Invalid or duplicate manifest path')
        paths.add(path)
        previous = expected[row['asset']].setdefault(row['sha256'], row['bytes'])
        if previous != row['bytes']:
            raise ValueError('Inconsistent object size')
    checked = 0; total = 0
    for asset in manifest['assets']:
        name = asset['name']
        if Path(name).name != name:
            raise ValueError('Unsafe asset name')
        source = assets / name
        if source.stat().st_size != asset['bytes'] or digest(source) != asset['sha256']:
            raise ValueError('Changed bundle asset: ' + name)
        objects = expected.pop(name)
        with zipfile.ZipFile(source) as archive:
            names = archive.namelist()
            if len(names) != len(objects) or set(names) != {'objects/' + key for key in objects}:
                raise ValueError('Archive objects do not match all declared paths')
            for checksum, size in objects.items():
                calculated = hashlib.sha256(); actual_size = 0
                with archive.open('objects/' + checksum) as stream:
                    while block := stream.read(4 * 1024**2):
                        calculated.update(block); actual_size += len(block)
                if calculated.hexdigest() != checksum or actual_size != size:
                    raise ValueError('Archived original file differs: ' + checksum)
                checked += 1; total += size
        print('ALL_OBJECTS_VERIFIED', name, checked, flush=True)
    if expected or checked != manifest['unique_objects'] or len(paths) != manifest['paths']:
        raise ValueError('Incomplete source-to-asset mapping')
    result = {'status': 'PASS', 'paths_verified': len(paths),
              'unique_objects_read_and_sha256_verified': checked,
              'original_unique_bytes_verified': total, 'assets_verified': len(manifest['assets']),
              'every_archive_object_checked': True, 'all_original_paths_mapped': True}
    write_json(report, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pack')
    p.add_argument('--root', type=Path, required=True); p.add_argument('--selection', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); p.add_argument('--part-limit', type=int, default=1_850_000_000)
    p = sub.add_parser('restore')
    p.add_argument('--manifest', type=Path, required=True); p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--destination', type=Path, required=True); p.add_argument('--prefix', action='append', default=[])
    p.add_argument('--keep-identical-existing', action='store_true')
    p = sub.add_parser('verify')
    p.add_argument('--manifest', type=Path, required=True); p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'pack':
        pack(args.root, args.selection, args.output, args.part_limit)
    elif args.command == 'restore':
        print(json.dumps(restore(args.manifest, args.assets, args.destination, args.prefix, args.keep_identical_existing)))
    else:
        print(json.dumps(verify_bundle(args.manifest, args.assets, args.report)))
