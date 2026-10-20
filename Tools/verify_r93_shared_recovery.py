"""Verify restored R93 files and the unchanged data readers of five experiments.

This runs CPU data preparation only. It does not train or choose a model, open
the sealed holdout, or overwrite an original scientific result.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ['CUDA_VISIBLE_DEVICES'] = ''

ROUNDS = {
    93: ('R93_RecoverableDetailSeparatedScratch', 'train_r93.py', 60, None),
    94: ('R94_EvidenceConditionalScratch', 'r94_dataset.py', 8, 940041),
    95: ('R95_CounterfactualGateRepairScratch', 'r95_dataset.py', 48, 950041),
    97: ('R97_DirectCausalPhaseScratch', 'r97_dataset.py', 48, 970043),
    98: ('R98_AggressiveTextureScratch', 'r98_dataset.py', 48, 980047),
}
CONTENT_ID = '6494719ad21665723ba32cdcb3871a40691753ca03791f181416349f02fd31a5'


def read_json(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fingerprint(value):
    import numpy as np
    import torch
    if isinstance(value, torch.Tensor):
        value = value.detach().cpu().contiguous().numpy()
    if isinstance(value, np.ndarray):
        return {'dtype': str(value.dtype), 'shape': list(value.shape),
                'sha256': hashlib.sha256(value.tobytes()).hexdigest()}
    if isinstance(value, dict):
        return {key: fingerprint(v) for key, v in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [fingerprint(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def reader_reference(root, package, rounds=tuple(ROUNDS)):
    import torch
    torch.set_num_threads(1)
    manifest = read_json(package / 'manifest.json')
    if manifest.get('content_sha256') != CONTENT_ID:
        raise ValueError('This is not the frozen R93 formal data used by R94-R98')
    result = {}
    for number in rounds:
        name, filename, epoch, seed = ROUNDS[number]
        source = root / 'Experiments' / name / 'training' / filename
        spec = importlib.util.spec_from_file_location('recovered_r' + str(number), source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        cls = getattr(module, f'R{number}SceneDataset')
        options = {} if seed is None else {'master_seed': seed}
        # R94 ended with a failed eighth epoch, before its proposed final stage.
        patch, core = (512, 256) if number == 94 else (896, 512)
        dataset = cls(package, manifest, 'train', patch, core, epoch, **options)
        roles = defaultdict(list)
        for index, (record, observations) in enumerate(dataset.items):
            roles[record['role']].append(index)
        indices = sorted({0, len(dataset)//2, len(dataset)-1,
                          *[values[0] for values in roles.values()]})
        samples = {}
        for index in indices:
            samples[str(index)] = fingerprint(dataset[index])
            print('NATIVE_READER_SAMPLE', number, index, flush=True)
        result[name] = {'available_examples': len(dataset), 'roles': sorted(roles),
                        'indices': indices, 'values': samples, 'reader_sha256': sha(source),
                        'patch_size': patch, 'core_size': core, 'epoch': epoch, 'seed': seed}
    return result


def verify_files(package, catalog):
    specifications = read_json(catalog)
    rows = specifications['files']
    expected = {row['path'] for row in rows}
    if len(expected) != 15004 or len(rows) != len(expected):
        raise ValueError('Invalid frozen file set')
    found = {path.relative_to(package).as_posix() for path in package.rglob('*') if path.is_file()}
    if found != expected:
        raise ValueError('Restored data file set differs from the frozen package')
    resolved = package.resolve()
    for index, row in enumerate(rows, 1):
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe frozen data path')
        path = package / relative
        if not path.resolve().is_relative_to(resolved):
            raise ValueError('Restored data redirects outside its new location')
        if path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('Restored file differs: ' + row['path'])
        if index % 2000 == 0:
            print('FROZEN_FILES_VERIFIED', index, len(rows), flush=True)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--file-catalog', type=Path)
    parser.add_argument('--rounds', nargs='+', type=int, choices=ROUNDS, default=list(ROUNDS))
    parser.add_argument('--skip-file-check', action='store_true',
                        help='Only compare representative native-reader values, without a full file audit')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError('Keep the previous verification report')
    root = args.root.resolve(strict=True)
    package = args.data_root or root / 'Experiments' / ROUNDS[93][0] / 'data/r93_formal'
    reference = args.reference or root / 'docs/reproducibility/r93_shared/READER_REFERENCE.json.gz'
    catalog = args.file_catalog or root / 'docs/reproducibility/r93_shared/FROZEN_FILES.json.gz'
    checked = 0 if args.skip_file_check else verify_files(package, catalog)
    expected = read_json(reference)['readers']
    actual = reader_reference(root, package, args.rounds)
    for name, values in actual.items():
        if values != expected[name]:
            raise ValueError('Native-reader values differ for ' + name)
    import cv2
    import numpy as np
    import torch
    result = {'status': 'PASS', 'dataset_content_sha256': CONTENT_ID,
              'full_frozen_file_set_verified': not args.skip_file_check, 'files_verified': checked,
              'readers_verified': list(actual),
              'representative_samples_verified': sum(len(value['indices']) for value in actual.values()),
              'all_eight_training_roles_covered_per_reader': all(len(v['roles']) == 8 for v in actual.values()),
              'all_prepared_input_target_branch_and_metadata_values_exact': True,
              'environment': {'python': sys.version.split()[0], 'numpy': np.__version__,
                              'opencv': cv2.__version__, 'torch': torch.__version__,
                              'torch_cuda_runtime': torch.version.cuda},
              'historical_training_repeated': False, 'sealed_holdout_read': False}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
