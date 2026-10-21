"""Read the original V42 log correctly and optionally replay two fixed models.

The historical CSV and trainer remain unchanged. Its header omits one value
written by the original function and names nine ANN values that it never writes.
This is a preservation/CPU check, not a repetition of the historical GPU run.
"""
import argparse
import ast
import contextlib
import gc
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import csv

from research_recovery import digest, safe_relative, write_json


def original_log_layout(source):
    """Execute only the original constant definitions, never the trainer."""
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    namespace = {}
    selected = []
    writer = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name == '_PROXY_BASE_KEYS' or name.startswith('_VAL_') and name != '_VAL_METRICS_DEFAULT':
                selected.append(node)
        if isinstance(node, ast.FunctionDef) and node.name == '_build_val_log_row':
            writer = node
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(source), 'exec'), namespace)
    if writer is None:
        raise ValueError('The original value writer is unavailable')
    names = {node.id for node in ast.walk(writer) if isinstance(node, ast.Name)}
    losses = namespace['_VAL_LOSS_SUMMARY_KEYS']
    if (len(losses) != len(namespace['_VAL_LOSS_HEADER_KEYS']) + 1
            or losses[8] != 'loss_input_lowfreq' or '_VAL_ANN_SEQ_KEYS' in names):
        raise ValueError('This is a different historical log writer; review its layout')
    original = list(namespace['_VAL_LOG_HEADER_V5'])
    corrected = [name for name in original if name not in namespace['_VAL_ANN_SEQ_KEYS']]
    corrected.insert(corrected.index('loss_phys') + 1, 'loss_input_lowfreq')
    if len(original) != 177 or len(corrected) != 169 or len(set(corrected)) != len(corrected):
        raise ValueError('Unexpected original column layout')
    return original, corrected, list(namespace['_VAL_ANN_SEQ_KEYS'])


def read_original_log(path, original, corrected):
    with path.open('r', encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.reader(stream))
    if not rows or rows[0] != original or any(len(row) != len(corrected) for row in rows[1:]):
        raise ValueError('The CSV differs from the exact original writer layout')
    epochs = [int(row[0]) for row in rows[1:]]
    if epochs != list(range(1, len(epochs) + 1)):
        raise ValueError('The original run does not have a continuous epoch sequence')
    return [dict(zip(corrected, row)) for row in rows[1:]], rows[1:]


def verify_stdout(rows, text):
    expression = re.compile(
        r'-> Epoch (\d+) Val Done\. Total=([\d.eE+\-]+) \| Rec=([\d.eE+\-]+)'
        r' \| Edge=([\d.eE+\-]+) \| EdgeProf=([\d.eE+\-]+)'
        r' \| PSNR=([\d.eE+\-]+) \| SSIM=([\d.eE+\-]+)')
    checks = 0
    by_epoch = {int(row['epoch']): row for row in rows}
    fields = ['val_total', 'val_rec', 'val_edge', 'val_edge_profile', 'val_psnr', 'val_ssim']
    for match in expression.finditer(text):
        epoch = int(match[1])
        if epoch == 0:
            # The unchanged trainer prints a before-training reference, which
            # is deliberately absent from its per-epoch CSV.
            continue
        if epoch not in by_epoch:
            raise ValueError('The stdout belongs to a different run')
        for field, printed in zip(fields, match.groups()[1:]):
            places = len(printed.split('.')[1]) if '.' in printed else 0
            if abs(float(by_epoch[epoch][field]) - float(printed)) > 0.50001 * 10 ** -places:
                raise ValueError('The recovered value disagrees with original stdout: ' + field)
            checks += 1
    if not checks:
        raise ValueError('No original validation records were checked')
    return checks


def replay_native(root, output, manifest, compare):
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    import torch
    import numpy as np
    import cv2
    torch.set_num_threads(1)
    cv2.setNumThreads(1)
    if torch.version.cuda is not None:
        raise ValueError('Use the checked CPU-only PyTorch environment')
    native_path = root / safe_relative(manifest['native_reader'])
    sys.path.insert(0, str(native_path.parent))
    spec = importlib.util.spec_from_file_location('preserved_lab_v42_native', native_path)
    native = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(native)
    original_ctor = native.GeoEdgeAlignSR_v1_v5_NoCoord
    inputs = output / 'inputs'
    inputs.mkdir()
    for row in manifest['inputs']:
        raw = cv2.imdecode(np.fromfile(root / safe_relative(row['source']), dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        if raw is None or raw.dtype != np.uint8:
            raise ValueError('The original full frame must be readable 8-bit camera-source data')
        x, y, w, h = row['crop_xywh']
        crop = raw[y:y+h, x:x+w]
        if crop.shape != (h, w):
            raise ValueError('The fixed crop is outside its source')
        ok, encoded = cv2.imencode('.bmp', crop)
        if not ok:
            raise ValueError('Cannot encode the fixed native input')
        encoded.tofile(inputs / (row['id'] + '.bmp'))
    cases = []
    for checkpoint in manifest['checkpoints']:
        captured = []
        def constructor(*args, **kwargs):
            model = original_ctor(*args, **kwargs)
            def record(_module, _inputs, value):
                captured.append(value.detach().cpu().numpy().astype(np.float32).copy())
            model.register_forward_hook(record)
            return model
        native.GeoEdgeAlignSR_v1_v5_NoCoord = constructor
        sys.argv = [str(native_path), '--weights', str(root / safe_relative(checkpoint['path'])),
                    '--input-dir', str(inputs), '--recon-root', str(output / checkpoint['id']),
                    '--output-name', 'fixed_inputs', '--device', 'cpu', '--strict-load', '--psf-from-ckpt',
                    '--anchor-output-mode', 'none']
        with (output / (checkpoint['id'] + '.log')).open('w', encoding='utf-8') as log, contextlib.redirect_stdout(log):
            native.main()
        if len(captured) != len(manifest['inputs']):
            raise ValueError('The native reader did not process all fixed inputs')
        for row, prediction in zip(sorted(manifest['inputs'], key=lambda r: r['id']), captured):
            paths = list((output / checkpoint['id']).rglob(row['id'] + '.bmp'))
            if len(paths) != 1 or not np.isfinite(prediction).all():
                raise ValueError('Missing or nonfinite original native output')
            key = checkpoint['id'] + '_' + row['id']
            np.save(output / (key + '.npy'), prediction, allow_pickle=False)
            import hashlib
            result = {'id': key, 'checkpoint_sha256': checkpoint['sha256'],
                      'checkpoint_state_kind': checkpoint['state_kind'],
                      'input_crop_bmp_sha256': digest(inputs / (row['id'] + '.bmp')),
                      'shape': list(prediction.shape), 'all_outputs_finite': True,
                      'full_native_float32_sha256': hashlib.sha256(prediction.tobytes()).hexdigest(),
                      'output_bmp_sha256': digest(paths[0])}
            if compare and result != next(item for item in compare if item['id'] == key):
                raise ValueError('The native CPU result differs from its fixed reference: ' + key)
            cases.append(result)
        del captured
        gc.collect()
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native', action='store_true', help='Also run the two explicitly pinned saved models on CPU')
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / 'docs/reproducibility/lab_comparisons/V42_SOURCE_FILES.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        path = root / safe_relative(row['path'])
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('A frozen V42 historical source differs: ' + row['path'])
    for row in manifest['checkpoints'] if args.native else []:
        path = root / safe_relative(row['path'])
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('A fixed V42 model differs: ' + row['path'])
    original, corrected, absent = original_log_layout(root / safe_relative(manifest['trainer']))
    prepared = []
    for run in manifest['runs']:
        rows, raw = read_original_log(root / safe_relative(run['csv']), original, corrected)
        text = (root / safe_relative(run['stdout'])).read_text(encoding='utf-8-sig')
        if run.get('original_stdout_empty'):
            if text:
                raise ValueError('The recorded empty historical stdout has changed')
            count = 0
        else:
            count = verify_stdout(rows, text)
        prepared.append((run, rows, raw, count))
    if args.output.exists():
        raise FileExistsError('Use a new owned output directory')
    args.output.mkdir(parents=True)
    checks = []
    for run, rows, raw, count in prepared:
        target = args.output / (run['id'] + '_correctly_labeled.csv')
        with target.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(corrected)
            writer.writerows(raw)
        checks.append({'run': run['id'], 'epochs': len(rows), 'all_original_numeric_tokens_retained': True,
                       'stdout_numeric_fields_checked': count,
                       'stdout_corroboration_available': not run.get('original_stdout_empty', False),
                       'last_validation': {key: rows[-1][key] for key in
                        ['epoch', 'val_total', 'val_rec', 'val_psnr', 'val_ssim', 'seq_val_score']}})
    native = replay_native(root, args.output, manifest, manifest.get('native_reference')) if args.native else []
    report = {'status': 'PASS_ORIGINAL_LOG_LAYOUT_AND_STDOUT', 'runs': checks,
              'original_header_columns': len(original), 'original_value_columns': len(corrected),
              'missing_original_header_field': 'loss_input_lowfreq',
              'named_but_never_written_ANN_columns': absent,
              'original_csv_or_trainer_modified': False, 'absent_ANN_values_fabricated': False,
              'native_cases': native, 'CPU_reference_matched': bool(native and manifest.get('native_reference')),
              'training_repeated': False, 'historical_GPU_outputs_claimed_bit_exact': False}
    write_json(args.output / 'V42_HISTORY_REPLAY_VERIFIED.json', report)
    print('V42_ORIGINAL_HISTORY_REPLAY_VERIFIED', sum(row['epochs'] for row in checks), len(native), flush=True)


if __name__ == '__main__':
    main()
