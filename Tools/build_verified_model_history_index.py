"""Describe model contents already recovered from GitHub, without loading again.

Original file identity, exact tensor identity, epoch metadata and resumability
are different facts. This index never selects a model or supplies restore paths;
final paths still require the global master binding.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import re

from build_project_restore_index import read, verify_exact_batch_receipt
from research_recovery import safe_relative, write_json


def state_equivalence_groups(objects):
    groups = defaultdict(list)
    for record in objects:
        for slot, fingerprint in record.get('state_dict_fingerprints', {}).items():
            if not fingerprint.get('tensors'):
                continue
            key = (fingerprint['sha256'], fingerprint['tensors'], fingerprint['elements_including_buffers'])
            groups[key].append({'file_sha256': record['sha256'], 'state_slot': slot,
                                'recorded_epoch': record.get('recorded_epoch')})
    return [{'tensor_content_sha256': key[0], 'tensors': key[1], 'elements_including_buffers': key[2],
             'different_serialized_files': len({row['file_sha256'] for row in values}), 'states': values}
            for key, values in sorted(groups.items()) if len(values) > 1]


def epoch_name_differences(objects):
    findings = []
    for record in objects:
        epoch = record.get('recorded_epoch')
        if not isinstance(epoch, (int, float)) or not math.isfinite(epoch):
            continue
        for location in record['original_locations']:
            filename = Path(location['logical_path']).name
            match = re.fullmatch(r'epoch_(\d+)\.(?:pth\.tar|pth|pt|ckpt)', filename, re.IGNORECASE)
            if match and int(match[1]) != epoch:
                findings.append({'path': location['logical_path'], 'file_sha256': record['sha256'],
                                 'filename_epoch': int(match[1]), 'checkpoint_recorded_epoch': epoch,
                                 'source_modified_or_epoch_reinterpreted': False})
    return findings


def build(plan_path, output):
    if output.exists():
        raise FileExistsError('Keep the preceding verified index')
    plan = read(plan_path)
    objects = {}
    receipts = []
    for batch in plan['batches']:
        folder = Path(batch['folder'])
        receipt_path = folder / 'BATCH_GITHUB_RESTORE_VERIFIED.json'
        if not receipt_path.exists():
            raise ValueError('Complete the actual GitHub recovery before indexing: ' + batch['batch'])
        manifest = read(folder / 'bundle/RESEARCH_ASSETS.json.gz')
        receipt = read(receipt_path)
        verify_exact_batch_receipt(manifest, receipt)
        receipts.append({'batch': batch['batch'], 'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                         'objects': len(receipt['checks'])})
        for row in receipt['checks']:
            if row['sha256'] in objects:
                raise ValueError('A supposedly new model object occurs in two batches')
            record = {key: value for key, value in row.items()
                      if key not in ['original_project_path', 'scope']}
            epoch = record.get('recorded_epoch')
            if isinstance(epoch, float) and not math.isfinite(epoch):
                record['recorded_epoch'] = {'nonfinite_original_metadata': repr(epoch)}
            record.update({'batch': batch['batch'], 'original_locations': []})
            objects[row['sha256']] = record
    if len(objects) != plan['new_unique_objects']:
        raise ValueError('The restored object total differs from the reviewed plan')
    other_objects = set()
    source_positions = 0
    for line in gzip.open(plan_path.parent / 'ALL_MODEL_LOCATIONS.jsonl.gz', 'rt', encoding='utf-8'):
        row = json.loads(line)
        source_positions += 1
        if row['sha256'] not in objects:
            other_objects.add((row['sha256'], row['bytes']))
            continue
        if row['bytes'] != objects[row['sha256']]['bytes']:
            raise ValueError('An original model position has a conflicting size')
        relative = safe_relative(row['logical_path']).as_posix()
        objects[row['sha256']]['original_locations'].append({
            'logical_path': relative, 'origin': row['origin'], 'scope': row['scope'],
            'plan_restore_path_not_final': row.get('restore_path', relative)})
    if source_positions != plan['source_files'] or any(not row['original_locations'] for row in objects.values()):
        raise ValueError('The index does not cover the captured original model positions')
    rows = [objects[key] for key in sorted(objects)]
    groups = state_equivalence_groups(rows)
    differences = epoch_name_differences(rows)
    exceptions = [row for row in rows if row['load_status'] != 'LOADABLE' or row.get('all_tensors_finite') is False]
    scope_counts = Counter(location['scope'] for row in rows for location in row['original_locations'])
    summary = {'status': 'ALL_NEW_MODEL_OBJECTS_ACTUALLY_RECOVERED_AND_CONTENT_INDEXED',
               'collection_tag': plan['tag'], 'actual_recovery_batches': len(receipts),
               'captured_all_model_positions': source_positions,
               'new_unique_objects_indexed': len(rows),
               'new_object_original_positions': sum(len(row['original_locations']) for row in rows),
               'other_already_preserved_unique_objects_not_reinspected_by_this_index': len(other_objects),
               'new_unique_file_bytes': sum(row['bytes'] for row in rows),
               'load_status_counts': dict(Counter(row['load_status'] for row in rows)),
               'loadable_objects_with_finite_tensors': sum(row.get('all_tensors_finite') is True for row in rows),
               'objects_with_saved_optimizer': sum(row.get('has_optimizer_state') is True for row in rows),
               'objects_with_recorded_epoch': sum('recorded_epoch' in row for row in rows),
               'tensor_equivalent_groups_with_multiple_serialized_files': sum(row['different_serialized_files'] > 1 for row in groups),
               'exact_filename_vs_recorded_epoch_differences': differences,
               'source_scope_counts': dict(scope_counts), 'batch_receipts': receipts,
               'global_master_restore_path_binding_pending': True, 'collection_publication_pending': True,
               'inference_or_training_repeated': False, 'scientific_model_selection_changed': False,
               'identical_model_tensors_imply_identical_optimizer_RNG_or_exact_training_resume': False}
    output.mkdir(parents=True)
    index = {'schema': 1, 'status': summary['status'], 'summary': summary,
             'objects': rows, 'tensor_equivalence_groups': groups, 'inspection_exceptions': exceptions,
             'not_a_restore_manifest': True}
    with gzip.open(output / 'MODEL_HISTORY_CONTENT_INDEX.json.gz', 'wt', encoding='utf-8', compresslevel=6) as stream:
        json.dump(index, stream, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    write_json(output / 'MODEL_HISTORY_INDEX_SUMMARY.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.plan, args.output)
    print('VERIFIED_MODEL_CONTENT_INDEX_BUILT', result['new_unique_objects_indexed'],
          result['new_object_original_positions'], flush=True)
