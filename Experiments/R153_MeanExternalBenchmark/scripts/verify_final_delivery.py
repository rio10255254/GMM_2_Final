"""Audit the complete ten-method handoff using saved observations, without inference or refitting."""
from pathlib import Path
import datetime
import json
import re
import sys
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from study import read, save, sha, MOSR_SOURCE, RECORD
from scripts.monitor_training import ORDER, completion, processes
import cv2
import numpy as np
import pandas as pd
from PIL import Image
PROJECT_ROOT = Path(__file__).resolve().parents[3]

METHODS = ['RAW', 'Wiener', 'EDSR-x1', 'NAFNet', 'RDN-x1', 'RCAN-x1',
           'Restormer', 'USRNet-x1', 'SwinIR', 'MOSR']


def independent_statistics(centers, diameters, radial, pi, direction, draws, weights, sem):
    result = {}
    boot = {}
    shape = radial - radial.mean(axis=-1, keepdims=True)
    for name, data in [('diameter_repeat_sd_nm', diameters),
                       ('contour_repeat_sd_nm', radial), ('shape_repeat_sd_nm', shape)]:
        result[name] = float(np.sqrt(np.var(data, axis=0, ddof=1).mean()))
        flat = data.reshape(30, -1)
        flat = flat - flat.mean(axis=0)
        gram = np.dot(flat, flat.T) / flat.shape[1]
        variance = (weights @ np.diag(gram) - np.einsum('bi,bi->b', weights @ gram, weights)) * 30 / 29
        boot[name] = np.sqrt(np.maximum(variance, 0))
    displacement_arrays = {}
    for kind in ('adjacent', 'start'):
        if kind == 'adjacent':
            difference = centers[:, 1:] - centers[:, :-1]
            reference = (pi[:, 1:] - pi[:, :-1]) * 1000
        else:
            difference = centers[:, 1:] - centers[:, :1]
            reference = (pi[:, 1:] - pi[:, :1]) * 1000
        displacement = np.einsum('rjkd,d->rjk', difference, direction).mean(axis=2) * 172.5
        error = displacement - reference
        displacement_arrays[kind] = (displacement, error)
        per_scan = {'mae': np.mean(np.abs(error), axis=1),
                    'rmse': np.mean(error ** 2, axis=1), 'bias': error.mean(axis=1)}
        for name, values in per_scan.items():
            key = kind + '_' + name + '_nm'
            result[key] = float(np.sqrt(values.mean()) if name == 'rmse' else values.mean())
            sample = values[draws].mean(axis=1)
            boot[key] = np.sqrt(sample) if name == 'rmse' else sample
        if kind == 'adjacent':
            variance = np.var(displacement, axis=1, ddof=1)
            result['pooled_within_scan_sd_nm'] = float(np.sqrt(variance.mean()))
            boot['pooled_within_scan_sd_nm'] = np.sqrt(variance[draws].mean(axis=1))
        else:
            endpoint = error[:, -1]
            for name, values in [('bias', endpoint), ('mae', np.abs(endpoint))]:
                key = 'endpoint_' + name + '_nm'
                result[key] = float(values.mean())
                boot[key] = values[draws].mean(axis=1)
    for label, reference in [('SEM_workbook', sem['workbook_diameter_nm']),
                             ('SEM_contour', sem['contour_diameter_nm'])]:
        key = label + '_diameter_MAE_nm'
        result[key] = float(np.abs(diameters.mean(axis=(0, 1)) - reference).mean())
        boot[key] = np.abs(weights @ diameters.mean(axis=1) - reference).mean(axis=1)
    for candidate, reference in enumerate(sem['radial_candidates_nm'], 1):
        for name, error in [('full_radial_difference_nm', np.abs(radial - reference)),
                            ('de_size_shape_difference_nm', np.abs(shape - (reference - reference.mean(axis=-1, keepdims=True))))]:
            key = 'SEM_candidate' + str(candidate) + '_' + name
            result[key] = float(error.mean())
            boot[key] = weights @ error.mean(axis=(1, 2, 3))
    return result, boot, displacement_arrays


def main():
    managers, workers = processes()
    assert not managers and not workers, 'Training still active'
    for method in ORDER:
        done = completion(method)
        assert done is not None and done['real_data_used_in_training_or_selection'] is False
        test = read(ROOT / 'runs' / method / 'synthetic_test.json')
        assert test['parents'] == len(test['parents_detail']) == 128
    swin_training = completion('SwinIR')
    assert swin_training['epochs_trained'] == 8
    directory = ROOT / 'reports/FINAL_BENCHMARK_THESIS_HANDOFF'
    handoff = read(ROOT / 'results/full_benchmark/handoff_verified.json')
    manifest = read(directory / 'MANIFEST.json')
    assert handoff['state'] == 'passed' and manifest['completed_scope'] == METHODS
    assert manifest['full_external_benchmark_complete']
    assert set(manifest['blocked_official_backends']) == {'U-Net', 'MambaIRv2'}
    assert sha(handoff['archive']) == handoff['archive_sha256']
    for file in manifest['files']:
        assert sha(directory / file['file']) == file['sha256'], file['file']
    with zipfile.ZipFile(handoff['archive']) as archive:
        assert archive.testzip() is None
    for document in ['REPORT.md', 'PAPER_UPDATE_GUIDE.md']:
        text = (directory / document).read_text(encoding='utf-8')
        assert not re.search(r'\bR(?:140|148|150|152|153)\b', text)
        for link in re.findall(r'\]\(([^)]+)\)', text):
            assert (directory / link).is_file(), link
    report = (directory / 'REPORT.md').read_text(encoding='utf-8')
    for required in ['MOSR完整架構', '完整合成測試摘要', '8192', '九方法', '135次', 'SwinIR', '15次', '128次', 'USRNet-x1首次']:
        assert required in report, required
    tables = ROOT / 'reports/data/full_benchmark'
    counts = {'summary.csv': 10, 'per_scan.csv': 600, 'per_position.csv': 600,
              'all_displacements.csv': 18000, 'paired_intervals.csv': 162,
              'runtime_samples.csv': 150, 'failures.csv': 10}
    for name, rows in counts.items():
        assert len(pd.read_csv(tables / name)) == rows, name
    summary = pd.read_csv(tables / 'summary.csv').set_index('method')
    failure = pd.read_csv(tables / 'failures.csv')
    assert (failure.complete_valid_scans == 30).all() and (failure.failed_pillars == 0).all()
    old_summary = pd.read_csv(ROOT / 'reports/data/completed_models/summary.csv').set_index('method')
    numeric = list(old_summary.select_dtypes(include='number').columns)
    np.testing.assert_allclose(summary.loc[old_summary.index, numeric], old_summary[numeric], atol=1e-8, rtol=0)
    old_pairs = pd.read_csv(ROOT / 'reports/data/completed_models/paired_intervals.csv').set_index(['reference_method', 'metric'])
    pairs = pd.read_csv(tables / 'paired_intervals.csv').set_index(['reference_method', 'metric'])
    pair_columns = ['reference', 'MOSR', 'difference', 'CI95_low', 'CI95_high']
    np.testing.assert_allclose(pairs.loc[old_pairs.index, pair_columns], old_pairs[pair_columns], atol=1e-8, rtol=0)
    samples = pd.read_csv(tables / 'runtime_samples.csv')
    old_samples = pd.read_csv(ROOT / 'reports/data/completed_models/runtime_samples.csv')
    pd.testing.assert_frame_equal(samples[samples.method != 'SwinIR'].reset_index(drop=True), old_samples, check_exact=True)
    baseline_runtime = read(ROOT / 'results/runtime/MOSR.json')
    for method in METHODS:
        runtime = read(ROOT / 'results/runtime' / (method + '.json'))
        assert runtime['frame_numbers'] == [0, 465, 929] and len(runtime['frames']) == 3
        assert runtime['gpu'] == baseline_runtime['gpu'] and runtime['torch_version'] == baseline_runtime['torch_version']
        assert runtime['precision'] == 'FP32' and runtime['batch'] == 1 and runtime['TF32'] is False
        assert runtime['warmup_per_frame'] == 2 and all(len(frame['samples']) == 5 for frame in runtime['frames'])
        assert [f['source_sha256'] for f in runtime['frames']] == [f['source_sha256'] for f in baseline_runtime['frames']]
    plan = read(MOSR_SOURCE / 'evaluation/capture_plan.json')
    calibration = read(MOSR_SOURCE / 'evaluation/calibration.json')
    runs = [run['run'] for run in plan['runs']]
    pi = np.array([[f['pi_y_um'] for f in sorted((f for f in plan['frames'] if f['run'] == run), key=lambda f: f['index'])] for run in runs])
    source_centers = []
    source_diameters = []
    source_points = []
    for run in runs:
        folder = ROOT / 'results/readouts/SwinIR'
        frame = pd.read_csv(folder / (run + '.csv')).sort_values(['index', 'pillar_id'])
        assert len(frame) == 279 and frame.valid.all()
        assert frame.groupby('index').pillar_id.apply(list).tolist() == [list(range(1, 10))] * 31
        source_centers.append(frame[['center_x_px', 'center_y_px']].to_numpy().reshape(31, 9, 2))
        source_diameters.append(frame.radius_px.to_numpy().reshape(31, 9) * 345)
        with np.load(folder / (run + '.npz'), allow_pickle=False) as data:
            source_points.append(data['points'])
        metadata = read(folder / (run + '.json'))
        assert metadata['failed_pillars'] == 0 and len(metadata['verified_outputs']) == 31
        assert metadata['reader_sha256'] == sha(ROOT / 'evaluation/measurement_interface.py')
        assert metadata['core_sha256'] == sha(ROOT / 'evaluation/reference_circle_core.py')
        for original, measured in zip(sorted((f for f in plan['frames'] if f['run'] == run), key=lambda f: f['index']), metadata['verified_outputs']):
            index = original['index']
            path = ROOT / 'results/reconstruction/SwinIR' / run / f'{index+1:02d}.npz'
            receipt = read(path.with_suffix('.json'))
            assert path.is_file() and receipt['source_sha256'] == original['source']['sha256'] == measured['source_sha256']
            assert receipt['output_sha256'] == measured['output_sha256']
            assert receipt['checkpoint_sha256'] == swin_training['checkpoint_sha256']
            assert receipt['mode'] == 'native_full_frame' and receipt['shape'] == [1544, 2064] and receipt['dtype'] == 'float32'
            assert receipt['post_sharpen_registration_diameter_or_contrast_correction'] is False
    centers = np.array(source_centers)
    diameters = np.array(source_diameters)
    points = np.array(source_points)
    assert centers.shape == (30, 31, 9, 2) and points.shape == (30, 31, 9, 64, 2)
    angles = np.linspace(0, 2*np.pi, 720, endpoint=False)
    radial = []
    for boundary, center in zip(points.reshape(-1, 64, 2), centers.reshape(-1, 2)):
        delta = boundary - center
        theta = np.arctan2(delta[:, 1], delta[:, 0])
        radial.append(np.interp(angles, theta, np.hypot(delta[:, 0], delta[:, 1]), period=2*np.pi))
    radial = np.array(radial).reshape(30, 31, 9, 720) * 172.5
    with np.load(ROOT / 'results/full_benchmark/SwinIR_measurements.npz', allow_pickle=False) as cached:
        np.testing.assert_allclose(cached['radial_nm'], radial, atol=1e-8, rtol=0)
        np.testing.assert_array_equal(cached['centers_px'], centers)
        np.testing.assert_array_equal(cached['diameters_nm'], diameters)
    with np.load(ROOT / 'results/full_benchmark/fixed_SEM_reference.npz', allow_pickle=False) as data:
        sem = {name: data[name] for name in data.files}
    draws = np.random.default_rng(20261002).integers(30, size=(20000, 30))
    weights = np.stack([np.bincount(row, minlength=30) for row in draws]) / 30
    with np.load(RECORD / 'data/complete_saved_boundary_points_RAW_R152.npz', allow_pickle=False) as original:
        assert original['run_ids'].tolist() == runs
        mcenters = original['R152_centers_px']
        mdiameters = original['R152_diameters_nm']
    with np.load(ROOT / 'results/full_benchmark/MOSR_measurements.npz', allow_pickle=False) as data:
        mradial = data['radial_nm']
    smetrics, sboot, displacement_arrays = independent_statistics(centers, diameters, radial, pi, calibration['axis_unit_vector'], draws, weights, sem)
    mmetrics, mboot, _ = independent_statistics(mcenters, mdiameters, mradial, pi, calibration['axis_unit_vector'], draws, weights, sem)
    metric_max_error = max(abs(value - summary.loc['SwinIR', key]) for key, value in smetrics.items())
    assert metric_max_error < 1e-7
    interval_max_error = 0.
    for key in sboot:
        interval = np.quantile(mboot[key] - sboot[key], [.025, .975])
        expected = pairs.loc[('SwinIR', key), ['CI95_low', 'CI95_high']].to_numpy(dtype=float)
        interval_max_error = max(interval_max_error, float(np.max(np.abs(interval - expected))))
        np.testing.assert_allclose(interval, expected, atol=1e-7, rtol=0)
    all_displacements = pd.read_csv(tables / 'all_displacements.csv')
    for kind, (displacement, error) in displacement_arrays.items():
        published = all_displacements[(all_displacements.method == 'SwinIR') & (all_displacements.kind == kind)].sort_values(['scan', 'step'])
        np.testing.assert_allclose(published.displacement_nm, displacement.ravel(), atol=1e-7, rtol=0)
        np.testing.assert_allclose(published.error_nm, error.ravel(), atol=1e-7, rtol=0)
    for number in [0, 465, 929]:
        frame = plan['frames'][number]
        path = ROOT / 'results/reconstruction/SwinIR' / frame['run'] / f'{frame["index"]+1:02d}.npz'
        assert sha(path) == read(path.with_suffix('.json'))['output_sha256']
        assert sha(frame['source']['path']) == frame['source']['sha256']
    with np.load(directory / 'fixed_region_pixels.npz', allow_pickle=False) as crops:
        assert crops['methods'].tolist() == METHODS and crops['crops'].shape == (10, 48, 48)
        bounds = crops['bounds_px']
        frame = plan['frames'][465]
        for i, method in enumerate(METHODS):
            if method == 'RAW':
                data = cv2.imread(frame['source']['path'], cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
            else:
                folder = MOSR_SOURCE / 'results/reconstruction' if method == 'MOSR' else ROOT / 'results/reconstruction' / method
                with np.load(folder / frame['run'] / f'{frame["index"]+1:02d}.npz', allow_pickle=False) as image:
                    data = image['output']
            np.testing.assert_array_equal(crops['crops'][i], data[bounds[1]:bounds[3], bounds[0]:bounds[2]])
    for image in directory.rglob('*.png'):
        pixels = np.asarray(Image.open(image).convert('RGB'))
        assert np.array_equal(pixels[:, :, 0], pixels[:, :, 1]) and np.array_equal(pixels[:, :, 1], pixels[:, :, 2]), image
    for row in read(ROOT / 'config/source_lock.json')['files']:
        assert sha(str(PROJECT_ROOT / row['path'])) == row['sha256']
    old_archive = read(ROOT / 'config/USER_RESUME_20261006.json')
    assert sha(str(PROJECT_ROOT / old_archive['completed_nine_method_archive'])) == old_archive['completed_nine_method_archive_sha256']
    result = {'state': 'passed', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': METHODS, 'scans_per_method': 30, 'frames_per_method': 930,
              'readouts_per_method': 8370, 'failures': 0, 'runtime_samples': 150,
              'paired_intervals': 162, 'old_nine_method_metrics_intervals_and_135_samples_unchanged': True,
              'SwinIR_independently_recomputed_displacements': 1800,
              'SwinIR_independent_metric_count': len(smetrics), 'SwinIR_metric_max_abs_error_nm': metric_max_error,
              'SwinIR_independent_interval_count': len(sboot), 'SwinIR_interval_max_abs_error_nm': interval_max_error,
              'SwinIR_all930_source_weight_strategy_and_readout_receipts_verified': True,
              'same_fixed_region_native_pixels_verified': True, 'all_raster_figures_grayscale': True,
              'protected_sources_and_nine_method_archive_unchanged': True,
              'public_report_links_manifest_and_zip_verified': True,
              'archive_sha256': sha(handoff['archive']), 'visual_review_still_required': True}
    save(ROOT / 'results/full_benchmark/independent_delivery_verified.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
