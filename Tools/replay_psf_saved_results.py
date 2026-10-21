"""Replay fixed optical-calibration results without fitting or using a GPU.

The small kit contains the original 100-position fit, 45 repeated-fit result
sets, original readers, and original result references. A separate display
view uses recorded source positions; the original 1x100 MAT is never changed.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def compare_values(actual, expected, path='root', counts=None):
    if counts is None:
        counts = {'numeric_fields': 0, 'relocated_path_fields': 0}
    if path == 'root.generated_at':
        return counts
    if isinstance(expected, dict):
        if set(actual) != set(expected):
            raise ValueError('Original saved result fields differ: ' + path)
        for key, value in expected.items():
            compare_values(actual[key], value, path + '.' + key, counts)
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError('Original saved array length differs: ' + path)
        for index, value in enumerate(expected):
            compare_values(actual[index], value, f'{path}[{index}]', counts)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        equal = (math.isnan(expected) and math.isnan(actual)) if isinstance(expected, float) and math.isnan(expected) else math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-10)
        if not equal:
            raise ValueError(f'Original saved number differs at {path}: {actual!r} versus {expected!r}')
        counts['numeric_fields'] += 1
    elif path.endswith(('.manifest_path', '.outputs_dir')):
        # Only these two recorded location fields relocate. Their research-
        # relative suffix must still be the exact same original result source.
        suffix = str(expected).replace('\\', '/').split('/PSF_Fitting/', 1)[-1]
        if not str(actual).replace('\\', '/').endswith('/' + suffix):
            raise ValueError('An original result was replaced by another source: ' + path)
        counts['relocated_path_fields'] += 1
    elif actual != expected:
        raise ValueError('Original saved metadata differs: ' + path)
    return counts


def map_recorded_positions(mat, csv_rows):
    import numpy as np
    rows = np.asarray(mat['source_row_map']).ravel().astype(int)
    cols = np.asarray(mat['source_col_map']).ravel().astype(int)
    ids = np.asarray(mat['source_file_index_map']).ravel().astype(int)
    if not (len(rows) == len(cols) == len(ids) == len(csv_rows)):
        raise ValueError('The original position maps and CSV do not cover the same fits')
    nr, nc = int(rows.max()), int(cols.max())
    positions = list(zip(rows.tolist(), cols.tolist()))
    if min(rows) != 1 or min(cols) != 1 or len(set(positions)) != nr * nc:
        raise ValueError('A complete unique physical position map is required')
    by_id = {int(row['file_index']): row for row in csv_rows}
    if len(by_id) != len(ids) or set(by_id) != set(ids.tolist()):
        raise ValueError('The original fit identities do not match the original CSV')
    for fi, row, col in zip(ids, rows, cols):
        source = by_id[int(fi)]
        if (int(source['source_row']), int(source['source_col'])) != (row, col):
            raise ValueError('Recorded source position disagrees between MAT and CSV')
    result = {}
    for key, leading in [('psf_grid', 2), ('coef_grid', 1), ('fval_map', 0), ('iterations_map', 0)]:
        array = np.asarray(mat[key])
        flat = array.reshape(array.shape[:leading] + (len(ids),))
        mapped = np.empty(array.shape[:leading] + (nr, nc), dtype=array.dtype)
        for i, (row, col) in enumerate(positions):
            mapped[..., row - 1, col - 1] = flat[..., i]
        for i, (row, col) in enumerate(positions):
            if not np.array_equal(mapped[..., row - 1, col - 1], flat[..., i]):
                raise ValueError('A physical display position changed the saved values')
        result[key] = mapped
    result['grid_rows'] = np.array([[nr]])
    result['grid_cols'] = np.array([[nc]])
    return result, positions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='Extracted small-kit directory')
    parser.add_argument('--output', type=Path, required=True, help='New output directory')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.output.exists():
        raise FileExistsError('Keep an earlier output and choose a new directory')
    identities = json.loads((root / 'PSF_REPLAY_INPUTS.json').read_text(encoding='utf-8'))
    for row in identities['files']:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe fixed input path')
        path = root / relative
        if not path.resolve().is_relative_to(root) or path.stat().st_size != row['bytes'] or sha(path) != row['sha256']:
            raise ValueError('An original replay input changed: ' + row['path'])
    args.output.mkdir(parents=True)
    psf_root = root / 'PSF_Fitting'
    sys.path.insert(0, str(psf_root))
    from quick_recalibration.validation_experiments import l0_newdata_analysis as l0
    from quick_recalibration.validation_experiments import l1_newdata_analysis as l1

    def relocated_trial_dir(value):
        relative = Path(str(value).replace('\\', '/'))
        if relative.is_absolute() or '..' in relative.parts or relative.drive:
            raise ValueError('Only the preserved relative trial locations are allowed')
        path = (psf_root / relative).resolve()
        if not path.is_relative_to(psf_root.resolve()):
            raise ValueError('An original trial redirects outside the downloaded kit')
        return path

    l0.resolve_trial_dir = relocated_trial_dir
    repeated = l0.json_ready(l1.build_l1_payload([1, 2, 3]))
    expected_l1 = json.loads((root / 'reference/L1_newdata_summary.json').read_text(encoding='utf-8'))
    repeated_checks = compare_values(repeated, expected_l1)
    (args.output / 'REPLAYED_L1.json').write_text(json.dumps(repeated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    helper = load_module('preserved_psf_report_helper', psf_root / 'PSF_Report_Helper/run_report_analysis.py')
    fit = psf_root / 'PSF_Fitting_ValidationLab/outputs/final_candidate_full100'
    mat_path, csv_path = fit / 'PSF_fitted_2D_FOVstack.mat', fit / 'batch_results.csv'
    helper.run_analysis(psf_root, psf_root / 'PSF_Report_Helper', args.output / 'original_storage_layout', mat_path, csv_path)
    with (root / 'reference/summary_stats.csv').open(encoding='utf-8-sig', newline='') as stream:
        expected_stats = list(csv.DictReader(stream))
    with (args.output / 'original_storage_layout/tables/summary_stats.csv').open(encoding='utf-8-sig', newline='') as stream:
        actual_stats = list(csv.DictReader(stream))
    if len(actual_stats) != len(expected_stats):
        raise ValueError('The original 100-fit summary length changed')
    count = 0
    for actual, expected in zip(actual_stats, expected_stats):
        if actual['metric'] != expected['metric']:
            raise ValueError('The original summary identities changed')
        for key in ['mean', 'std', 'min', 'max']:
            if not math.isclose(float(actual[key]), float(expected[key]), rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('The original 100-fit statistic changed')
            count += 1
    from scipy.io import loadmat, savemat
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        csv_rows = list(csv.DictReader(stream))
    original = loadmat(mat_path)
    physical, positions = map_recorded_positions(original, csv_rows)
    physical_mat = args.output / 'MAPPED_FOR_DISPLAY.mat'
    savemat(physical_mat, physical)
    helper.run_analysis(psf_root, psf_root / 'PSF_Report_Helper', args.output / 'recorded_physical_layout', physical_mat, csv_path)
    report = {'status': 'PASS_ORIGINAL_SAVED_RESULT_REPLAY', 'inputs_verified': len(identities['files']),
              'repeated_fit_arrays_and_summary': repeated_checks,
              'capture_rounds': 3, 'fit_repeats_per_capture': 15, 'sampled_FOV_positions': 9,
              'L1_status': repeated['summary']['status'], 'full100_original_summary_numbers': count,
              'full100_original_storage_shape': list(original['psf_grid'].shape),
              'full100_recorded_physical_shape': list(physical['psf_grid'].shape),
              'recorded_physical_positions': positions,
              'physical_display_all_saved_values_unchanged': True,
              'PSF_fitting_executed': False, 'GPU_used': False,
              'original_input_files_changed': False,
              'scope': 'Replay of existing fitted results; new physical display uses original source-row/column metadata. Does not repeat optical acquisition or optimization, establish absolute accuracy, or validate the Python tutorial preview as a fitter.'}
    (args.output / 'PSF_SAVED_RESULTS_REPLAY_VERIFIED.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('ORIGINAL_PSF_RESULTS_REPLAYED_AND_PHYSICAL_POSITIONS_VERIFIED', count, repeated_checks['numeric_fields'], flush=True)


if __name__ == '__main__':
    main()
