"""Create final component manifests from the verified global source-path map.

Per-batch plan paths are provisional. Only the global master resolves current
H references, older versions and all shared aliases consistently. No upload,
publication, deletion or scientific decision is performed by this command.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from collections import Counter, defaultdict

from build_project_restore_index import read, verify_exact_batch_receipt
from research_recovery import safe_relative, write_json


def bind(operation, master_path, output):
    if output.exists():
        raise FileExistsError('Keep a preceding reviewed collection binding')
    master = read(master_path)
    if master.get('state') != 'complete':
        raise ValueError('A completed verified global map is required')
    by_tag = defaultdict(list)
    for family in ['model', 'numeric', 'image', 'package']:
        plan = read(operation / (family + '_batches') / 'PLAN.json')
        for batch in plan['batches']:
            folder = Path(batch['folder'])
            by_tag[batch.get('tag', plan['tag'])].append((batch['batch'], folder / 'bundle/RESEARCH_ASSETS.json.gz', folder / 'BATCH_GITHUB_RESTORE_VERIFIED.json'))
    extra = operation / 'EXTRA_SCOPE_COLLECTIONS.json'
    if extra.exists():
        for item in read(extra)['collections']:
            by_tag[item['tag']].append((item['id'], Path(item['bundle_manifest']), Path(item['verification'])))
    recorded_checks = {(row['tag'], row['batch']): row['verification_sha256'] for row in master['batch_checks']}
    ready = []
    # Check every component first; never leave a partly approved output tree.
    for component in master['components']:
        if not component.get('new_collection'):
            continue
        source = master_path.parent / safe_relative(component['restore_manifest'])
        if hashlib.sha256(source.read_bytes()).hexdigest() != component['manifest_sha256']:
            raise ValueError('A global component map was changed')
        value = read(source)
        verified_objects = set()
        all_parts = {}
        receipts = []
        for batch, manifest_path, proof in by_tag[component['tag']]:
            if hashlib.sha256(proof.read_bytes()).hexdigest() != recorded_checks[(component['tag'], batch)]:
                raise ValueError('A restoration receipt changed after the global map')
            manifest, inspection = read(manifest_path), read(proof)
            verify_exact_batch_receipt(manifest, inspection)
            verified_objects.update((r['sha256'], r['bytes']) for r in inspection['checks'])
            for part in inspection['assets']:
                prior = all_parts.get(part['name'])
                if prior and (prior['bytes'], prior['sha256']) != (part['bytes'], part['sha256']):
                    raise ValueError('One release contains conflicting part identities')
                all_parts[part['name']] = part
            receipts.append({'batch': batch, 'receipt_sha256': recorded_checks[(component['tag'], batch)],
                             'unique_objects_checked': len(inspection['checks']),
                             'original_load_errors_preserved': inspection.get('load_errors_preserved', 0),
                             'original_nonfinite_states_preserved': inspection.get('nonfinite_histories_preserved', 0)})
        required = {(r['sha256'], r['bytes']) for r in value['files']}
        if not required <= verified_objects:
            raise ValueError('A final original path has no exactly restored object in this release')
        for part in value['assets']:
            actual = all_parts.get(part['name'])
            if actual is None or (actual['bytes'], actual['sha256']) != (part['bytes'], part['sha256']):
                raise ValueError('The final component references an unverified part')
        if any(r['path'].startswith('__archive_objects__/') for r in value['files']):
            raise ValueError('Internal object-store paths cannot be final original locations')
        ready.append((component, source, value, receipts, len(verified_objects - required)))
    output.mkdir(parents=True)
    summaries = []
    for component, source, value, receipts, duplicate_count in ready:
        folder = output / component['tag']
        folder.mkdir()
        (folder / 'RESEARCH_ASSETS.json.gz').write_bytes(source.read_bytes())
        summary = {k: v for k, v in value.items() if k != 'files'}
        write_json(folder / 'BUNDLE_SUMMARY.json', summary)
        proof = {'status': 'VERIFIED_GLOBAL_ORIGINAL_PATH_BINDING', 'tag': component['tag'],
                 'master_index_sha256': hashlib.sha256(master_path.read_bytes()).hexdigest(),
                 'original_paths': len(value['files']), 'unique_objects': len({r['sha256'] for r in value['files']}),
                 'scope_counts': dict(Counter(r['scope'] for r in value['files'])), 'batch_receipts': receipts,
                 'byte_identical_objects_preferred_from_another_verified_release': duplicate_count,
                 'publication_pending': True, 'scientific_validation_scope_unchanged': True}
        write_json(folder / 'COLLECTION_VERIFICATION.json', proof)
        summaries.append({'tag': component['tag'], 'folder': str(folder), 'paths': proof['original_paths'],
                          'unique_objects': proof['unique_objects']})
    write_json(output / 'BOUND_COLLECTIONS.json', {'status': 'READY_FOR_SERVER_METADATA_CHECK_AND_PUBLICATION', 'collections': summaries})
    return summaries


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation', type=Path, required=True)
    parser.add_argument('--master-index', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = bind(args.operation, args.master_index, args.output)
    print('VERIFIED_COLLECTIONS_BOUND_TO_GLOBAL_ORIGINAL_PATHS', len(result), flush=True)
