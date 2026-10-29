"""Verify matched contour rows independently and recompute historical LSC summaries."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import load, save, record, sha, now
import numpy as np
import pandas as pd
from scipy import ndimage
from scipy.io import loadmat
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def shift_mask(mask, dx, dy):
    out = np.zeros_like(mask)
    h, w = mask.shape
    x0, x1, y0, y1 = max(0, -dx), min(w, w-dx), max(0, -dy), min(h, h-dy)
    out[y0+dy:y1+dy, x0+dx:x1+dx] = mask[y0:y1, x0:x1]
    return out


def independent_metrics(truth, pred):
    a = truth & ~ndimage.binary_erosion(truth, np.ones((3, 3)), border_value=0)
    b = pred & ~ndimage.binary_erosion(pred, np.ones((3, 3)), border_value=0)
    distances = np.r_[ndimage.distance_transform_edt(~a)[b], ndimage.distance_transform_edt(~b)[a]]
    return dict(mean_boundary_px=float(distances.mean()), hd95_px=float(np.percentile(distances, 95, method='hazen')),
                iou=float(np.sum(truth & pred)/np.sum(truth | pred)),
                area_error_pct=float(100*abs(int(pred.sum())-int(truth.sum()))/truth.sum()),
                maximum_boundary_px=float(distances.max()))


def write_csv(table, path):
    with path.open('x', encoding='utf-8', newline='') as f:
        table.to_csv(f, index=False)


def main():
    out = ROOT / 'results/competitive_review'
    plan = load(out/'plan.json')
    prepared = load(out/'preparation.json')
    assert sha(prepared['inputs']['path']) == prepared['inputs']['sha256']
    assert all(sha(str(PROJECT_ROOT / x['path'])) == x['sha256'] for x in plan['sources'].values())
    d = loadmat(out/'inputs.mat')
    t = pd.read_csv(out/'measurements.csv')
    methods, refs = plan['methods'], plan['references']
    keys = ['reference', 'exposure', 'pillar', 'method']
    assert len(t) == 1080 and not t.duplicated(keys).any()
    assert set(t.method) == set(methods) and set(t.exposure) == {13, 14, 15}
    assert set(t.reference) == set(refs) and set(t.pillar) == set(range(1, 37))
    differences = {k: 0. for k in ['mean_boundary_px', 'hd95_px', 'iou', 'area_error_pct']}
    additional = []
    for row in t.itertuples(index=False):
        i, e, r, m = row.pillar-1, row.exposure-13, refs.index(row.reference), methods.index(row.method)
        mask = d['masks'][:, :, i, e, m].astype(bool)
        raw = d['masks'][:, :, i, e, 0].astype(bool)
        truth = d['truth_masks'][:, :, i, r].astype(bool)
        offset = np.array(ndimage.center_of_mass(truth))[::-1] - np.array(ndimage.center_of_mass(raw))[::-1]
        expected = np.where(offset >= 0, np.floor(offset+.5), np.ceil(offset-.5)).astype(int)
        dx, dy = int(row.Raw_shift_x), int(row.Raw_shift_y)
        assert np.array_equal(expected, [dx, dy])
        assert np.array_equal(expected, d['shifts'][i, e, r, :])
        moved = shift_mask(mask, dx, dy)
        assert moved.sum() == mask.sum()
        values = independent_metrics(truth, moved)
        for key in differences:
            error = abs(values[key] - getattr(row, key))
            differences[key] = max(differences[key], error)
            assert error < 1e-5, (key, error)
        assert abs(abs(row.SEM_circularity-row.predicted_circularity)-row.circularity_error) < 1e-10
        assert 0 < row.SEM_circularity <= 1 and 0 < row.predicted_circularity <= 1
        additional.append(dict(zip(keys, [row.reference, row.exposure, row.pillar, row.method]), **values))
    independent = pd.DataFrame(additional)
    t = t.merge(independent[keys+['maximum_boundary_px']], on=keys, validate='one_to_one')
    old_r128 = pd.read_csv(str(PROJECT_ROOT / plan['sources']['R128_measurements']['path']))
    old_r128 = old_r128[(old_r128.preset == 'primary') & old_r128.method.isin(['Raw', 'R128_PNG'])].copy()
    old_r128['method'] = old_r128.method.replace({'R128_PNG': 'R128_P_s1285002'})
    old_compare = t.merge(old_r128, on=keys, suffixes=('', '_previous'), validate='one_to_one')
    assert len(old_compare) == 432
    numeric = ['mean_boundary_px', 'hd95_px', 'iou', 'area_error_pct', 'perimeter_error_pct', 'circularity_error']
    previous_diffs = {k: float((old_compare[k]-old_compare[k+'_previous']).abs().max()) for k in numeric}
    assert max(previous_diffs.values()) < 1e-5
    metrics = numeric + ['maximum_boundary_px']
    per_pillar = t.groupby(['reference', 'method', 'pillar', 'fully_neural_interior'], as_index=False)[metrics].median()
    summary_rows, paired_rows = [], []
    for reference in refs:
        for scope in ['all_36', 'interior_16']:
            group = per_pillar[(per_pillar.reference == reference) & ((per_pillar.fully_neural_interior == 1) if scope == 'interior_16' else True)]
            for method in methods:
                a = group[group.method == method].set_index('pillar')
                assert len(a) == (16 if scope == 'interior_16' else 36)
                summary_rows.append(dict(reference=reference, scope=scope, method=method, pillars=len(a), **{k: float(a[k].median()) for k in metrics}))
                for baseline in ['Raw', 'R109_E48', 'R61v16']:
                    if baseline == method:
                        continue
                    b = group[group.method == baseline].set_index('pillar')
                    for metric in metrics:
                        change = (a[metric]-b[metric]) * (1 if metric == 'iou' else -1)
                        paired_rows.append(dict(reference=reference, scope=scope, method=method, baseline=baseline, metric=metric,
                                                median_paired_improvement=float(change.median()), improved=int((change > 1e-6).sum()),
                                                worsened=int((change < -1e-6).sum()), tied=int((change.abs() <= 1e-6).sum())))
    summary = pd.DataFrame(summary_rows)
    paired = pd.DataFrame(paired_rows)
    by_exposure = t.groupby(['reference', 'exposure', 'method'], as_index=False)[metrics].median()
    worst_local = t.groupby(['reference', 'method'], as_index=False)['maximum_boundary_px'].max()

    lsc = pd.read_csv(str(PROJECT_ROOT / plan['sources']['LSC_pairs']['path']))
    reported = pd.read_csv(str(PROJECT_ROOT / plan['sources']['LSC_summary']['path']))
    pair_keys = ['sequence', 'pair_rank_raw_locked', 'start_frame_index', 'end_frame_index']
    assert not lsc.duplicated(pair_keys+['method']).any()
    locked = set(map(tuple, lsc[lsc.method == 'Raw'][pair_keys].to_numpy()))
    assert len(locked) == 120
    assert all(set(map(tuple, g[pair_keys].to_numpy())) == locked for _, g in lsc.groupby('method'))
    assert np.allclose(lsc.measured_step_um, lsc.aggregate_dx_um.abs(), atol=1e-12, rtol=0)
    assert np.allclose(lsc.nominal_abs_error_nm, (lsc.measured_step_um-lsc.nominal_step_um).abs()*1000, atol=1e-9, rtol=0)
    assert np.allclose(lsc.cross_axis_abs_nm, lsc.aggregate_dy_um.abs()*1000, atol=1e-9, rtol=0)
    lsc_rows = []
    for method, g in lsc.groupby('method', sort=False):
        for sequence, sg in g.groupby('sequence', sort=False):
            assert len(sg) == 30
            lsc_rows.append(dict(scope='per_sequence', sequence=sequence, method=method, n_pairs=len(sg),
                                 step_sd_nm=float(sg.measured_step_um.std(ddof=1)*1000),
                                 mean_nominal_abs_error_nm=float(sg.nominal_abs_error_nm.mean()),
                                 median_within_grid_sd_nm=float(sg.within_grid_sd_nm.median()), median_cross_axis_abs_nm=float(sg.cross_axis_abs_nm.median())))
        lsc_rows.append(dict(scope='all_four_sequences', sequence='combined', method=method, n_pairs=len(g),
                             step_sd_nm=float(np.mean([sg.measured_step_um.std(ddof=1)*1000 for _, sg in g.groupby('sequence')])),
                             mean_nominal_abs_error_nm=float(g.nominal_abs_error_nm.mean()),
                             median_within_grid_sd_nm=float(g.within_grid_sd_nm.median()), median_cross_axis_abs_nm=float(g.cross_axis_abs_nm.median())))
    recomputed = pd.DataFrame(lsc_rows)
    matched = recomputed.merge(reported, on=['scope', 'sequence', 'method'], suffixes=('', '_reported'), validate='one_to_one')
    assert len(matched) == len(reported) == len(recomputed)
    lsc_diffs = {k: float((matched[k]-matched[k+'_reported']).abs().max()) for k in ['n_pairs', 'step_sd_nm', 'mean_nominal_abs_error_nm', 'median_within_grid_sd_nm', 'median_cross_axis_abs_nm']}
    assert max(lsc_diffs.values()) < 1e-8
    assert not any('R128' in m for m in lsc.method.unique())

    for name, data in [('independent_metrics', independent), ('per_pillar', per_pillar), ('summary', summary), ('paired_comparisons', paired), ('per_exposure', by_exposure), ('worst_local', worst_local), ('LSC_recomputed', recomputed)]:
        write_csv(data, out/(name+'.csv'))
    save(out/'verification.json', dict(verified_utc=now(), all_1080_contour_rows_recomputed=True,
        independent_numeric_max_differences=differences, circularity_difference_formula_verified=True,
        perimeter_and_digital_circularity_from_unchanged_MATLAB_regionprops=True,
        previous_Raw_and_R128_rows_max_differences=previous_diffs,
        all_Raw_derived_shifts_independently_verified=True, no_shift_clipping=True,
        same_120_LSC_pairs_for_all_five_historical_methods=True, historical_LSC_summary_max_differences=lsc_diffs,
        R128_formal_LSC_measured=False, no_new_inference_or_training=True, no_new_confirmation=True,
        sources_unchanged=all(sha(str(PROJECT_ROOT / x['path'])) == x['sha256'] for x in plan['sources'].values()),
        plan=record(out/'plan.json'), inputs=record(out/'inputs.mat'), measurements=record(out/'measurements.csv'), analysis=record(__file__)))
    print(summary[summary.scope == 'all_36'].to_string(index=False))
    print('\nLSC summaries independently reproduced:')
    print(recomputed[recomputed.scope == 'all_four_sequences'].to_string(index=False))
    print('\nR128 paired results:')
    print(paired[(paired.scope == 'all_36') & (paired.method == 'R128_P_s1285002') & paired.metric.isin(['mean_boundary_px','circularity_error','perimeter_error_pct'])].to_string(index=False))
    print('\nNumeric verification:', differences, lsc_diffs)


if __name__ == '__main__':
    main()
