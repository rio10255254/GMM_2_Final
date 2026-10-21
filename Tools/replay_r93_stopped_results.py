"""Recalculate the recorded R93 epoch selection from its saved 60-row log.

Only Python's standard library is needed. This replays an existing internal
selection; it does not refit images, train a model, or promote R93.
"""
import argparse
import csv
import json
import math
from pathlib import Path

AXES = {'detail': 'val_detail_axis', 'contour': 'val_contour_axis',
        'identity': 'val_identity_axis', 'motion_mean': 'val_motion_axis',
        'exposure': 'val_exposure_axis'}
METRICS = {'detail_ratio': 'val_detail_axis', 'contour_ratio': 'val_contour_axis',
           'identity_change_gray': 'val_identity_gray', 'motion_mae_px': 'val_motion_mae',
           'motion_p95_px': 'val_motion_p95', 'exposure_ratio': 'val_exposure_axis',
           'tile_mean_abs_gray': 'val_tile_gray', 'clear_texture_change_gray': 'val_clear_texture_gray',
           'signed_motion_bias_x_px': 'val_motion_bias_x',
           'signed_motion_bias_y_px': 'val_motion_bias_y',
           'degraded_texture_ratio': 'val_degraded_texture_ratio'}


def recalculate(log, saved):
    with log.open(encoding='utf-8-sig', newline='') as stream:
        all_rows = list(csv.DictReader(stream))
    epochs = [int(row['epoch']) for row in all_rows]
    if epochs != list(range(1, 61)):
        raise ValueError('The complete original 60-epoch history is required')
    first, last = saved['candidate_window']
    rows = [row for row in all_rows if first <= int(row['epoch']) <= last
            and all(row.get(key) not in ('', None) for key in AXES.values())]
    bounds = {key: (min(float(r[key]) for r in rows), max(float(r[key]) for r in rows))
              for key in AXES.values()}
    ranking = []
    for row in rows:
        regrets = {}
        for axis, key in AXES.items():
            low, high = bounds[key]
            regrets[axis] = (float(row[key]) - low) / (high - low) if high > low else 0.0
        ranking.append({'epoch': int(row['epoch']), 'worst_regret': max(regrets.values()),
                        'mean_regret': sum(regrets.values()) / len(regrets),
                        **{axis + '_regret': value for axis, value in regrets.items()}})
    selected = min(ranking, key=lambda r: (r['worst_regret'], r['mean_regret'], r['epoch']))['epoch']
    best = {axis: int(min(rows, key=lambda r: float(r[key]))['epoch']) for axis, key in AXES.items()}
    if selected != saved['balanced_candidate_epoch'] or best != saved['best_by_axis']:
        raise ValueError('Recalculated selection differs from the original result')
    checked = []
    for epoch in (48, 60):
        row = next(row for row in all_rows if int(row['epoch']) == epoch)
        for metric, key in METRICS.items():
            if metric not in saved['epoch_' + str(epoch)]:
                continue
            actual = float(row[key]); expected = saved['epoch_' + str(epoch)][metric]
            if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12):
                raise ValueError(f'Original metric differs: epoch {epoch}, {metric}')
            checked.append({'epoch': epoch, 'metric': metric, 'value': actual})
    if any(float(r['val_tile_gray']) != 0 for r in rows):
        raise ValueError('The recorded zero tile difference is not reproduced')
    return {'status': 'PASS', 'complete_log_rows': len(all_rows),
            'candidate_epochs': [int(r['epoch']) for r in rows],
            'balanced_candidate_epoch': selected, 'best_by_axis': best,
            'recorded_metrics_recalculated': checked,
            'last_complete_epoch': epochs[-1], 'planned_epochs': saved['planned_epochs'],
            'historical_stop_status': saved['stop_status'],
            'full_training_repeated': False, 'scientific_baseline_changed': False}, ranking


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new output directory')
    experiment = args.root / 'Experiments/R93_RecoverableDetailSeparatedScratch'
    saved = json.loads((experiment / 'results/post_stop_analysis_epoch060.json').read_text(encoding='utf-8-sig'))
    logs = list((experiment / 'runs').glob('training_R93_scratch_seed930041_*/training_log.csv'))
    if len(logs) != 1:
        raise ValueError('The original R93 formal log is missing or ambiguous')
    result, ranking = recalculate(logs[0], saved)
    args.output.mkdir(parents=True)
    (args.output / 'R93_SELECTION_REPLAY.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    with (args.output / 'R93_CANDIDATE_RANKING.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ranking[0])); writer.writeheader(); writer.writerows(ranking)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
