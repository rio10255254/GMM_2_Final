"""Independently recalculate packaged results from saved centers and PI; no refitting."""
from pathlib import Path
import json, sys
import numpy as np
import pandas as pd


def verify(packet):
    tables = packet / 'data'
    aggregate = pd.read_csv(tables / 'all_aggregated_displacements.csv')
    summary = pd.read_csv(tables / 'aggregation_summary.csv')
    positions = pd.read_csv(tables / 'per_step_across_scan_statistics.csv')
    intervals = pd.read_csv(tables / 'mean_median_paired_intervals.csv')
    rows = np.random.default_rng(20261002).integers(0, 30, size=(20000, 30))
    boots, points = {}, {}
    max_difference = 0.
    with np.load(packet / 'verification/fixed_center_reaggregation.npz', allow_pickle=False) as arrays:
        pi = arrays['PI_positions_um']
        assert pi.shape == (30, 31)
        for method in ['RAW', 'MOSR']:
            centers = arrays[method + '_centers_px']
            assert centers.shape == (30, 31, 9, 2) and np.isfinite(centers).all()
            for aggregation in ['mean', 'median']:
                errors = {}
                for kind, delta, reference in [
                    ('adjacent', np.diff(centers, axis=1), np.diff(pi, axis=1) * 1000),
                    ('start', centers[:, 1:] - centers[:, :1], (pi[:, 1:] - pi[:, :1]) * 1000)]:
                    displacement = (getattr(np, aggregation)(delta, axis=2) @ arrays['axis_unit_vector']) * .1725 * 1000
                    error = displacement - reference
                    errors[kind] = error
                    data = aggregate[(aggregate.method == method) & (aggregate.aggregation == aggregation) &
                                     (aggregate.kind == kind)].sort_values(['scan', 'step'])
                    assert len(data) == 900
                    assert not data.duplicated(['scan', 'step']).any()
                    for name, values in [('displacement_nm', displacement), ('error_nm', error), ('PI_displacement_nm', reference)]:
                        difference = float(np.max(np.abs(data[name].to_numpy() - values.ravel())))
                        max_difference = max(max_difference, difference)
                        assert difference < 1e-8, (method, aggregation, kind, name, difference)
                    expected = summary[(summary.method == method) & (summary.aggregation == aggregation) & (summary.kind == kind)].iloc[0]
                    for name, value in [('mae_nm', abs(error).mean()), ('rmse_nm', np.sqrt((error ** 2).mean())),
                                        ('signed_bias_nm', error.mean()), ('maximum_absolute_error_nm', abs(error).max())]:
                        assert abs(expected[name] - value) < 1e-8
                    position = positions[(positions.method == method) & (positions.aggregation == aggregation) & (positions.kind == kind)].sort_values('step')
                    for name, value in [('mean_displacement_nm', displacement.mean(0)), ('displacement_sd_nm', displacement.std(0, ddof=1)),
                                        ('mean_error_nm', error.mean(0)), ('error_sd_nm', error.std(0, ddof=1))]:
                        assert np.max(abs(position[name].to_numpy() - value)) < 1e-8
                    if kind == 'adjacent':
                        sd = displacement.std(1, ddof=1)
                        assert abs(expected['pooled_within_scan_sd_nm'] - np.sqrt((sd ** 2).mean())) < 1e-8
                        assert abs(expected['mean_scan_sd_nm'] - sd.mean()) < 1e-8
                        assert abs(expected['sd_of_scan_sds_nm'] - sd.std(ddof=1)) < 1e-8
                        adjacent = displacement
                    elif aggregation == 'mean':
                        assert np.max(abs(adjacent.cumsum(1) - displacement)) < 2e-11
                key = method, aggregation
                boots[key] = {'pooled_within_scan_sd_nm': np.sqrt(np.mean(sd[rows] ** 2, axis=1))}
                points[key] = {'pooled_within_scan_sd_nm': np.sqrt(np.mean(sd ** 2))}
                for kind in ['adjacent', 'start']:
                    e = errors[kind]
                    for name, values in [('mae', abs(e).mean(1)), ('bias', e.mean(1)), ('mse', (e ** 2).mean(1))]:
                        boots[key][kind + '_' + name] = values[rows].mean(1)
                        points[key][kind + '_' + name] = values.mean()
                e = errors['start'][:, -1]
                for metric, values in [('endpoint_bias', e), ('endpoint_mae', abs(e))]:
                    boots[key][metric] = values[rows].mean(1)
                    points[key][metric] = values.mean()
    checked = 0
    for row in intervals.itertuples():
        if row.comparison == 'MOSR minus RAW':
            left, right = ('MOSR', row.aggregation), ('RAW', row.aggregation)
        else:
            left, right = (row.method, 'mean'), (row.method, 'median')
        samples = boots[left][row.metric] - boots[right][row.metric]
        ci = np.quantile(samples, [.025, .975])
        assert abs(row.difference - (points[left][row.metric] - points[right][row.metric])) < 1e-8
        assert max(abs(ci - [row.paired_CI95_low, row.paired_CI95_high])) < 1e-8
        if pd.notna(row.reduction_percent):
            gains = 100 * (1 - boots[left][row.metric] / boots[right][row.metric])
            assert max(abs(np.quantile(gains, [.025, .975]) - [row.reduction_CI95_low, row.reduction_CI95_high])) < 1e-8
        checked += 1
    assert len(aggregate) == 7200 and len(pd.read_csv(tables / 'all_pillar_displacements.csv')) == 16200
    report = {'status': 'passed', 'saved_centers_per_method': 8370, 'scans': 30, 'frames_per_scan': 31,
              'pillars': 9, 'aggregated_displacement_rows': len(aggregate), 'paired_interval_rows_checked': checked,
              'maximum_displacement_csv_difference_nm': max_difference,
              'recalculation_source': 'packaged saved centers and original PI arrays, not rounded report values',
              'refits': 0, 'model_forward_calls': 0, 'bootstrap_draws': 20000, 'bootstrap_seed': 20261002}
    (packet / 'verification/independent_recalculation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    verify(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
