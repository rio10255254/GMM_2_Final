"""Recompute closed-run numbers from preserved tables, without training or GPUs.

R95's first epoch-9 row was superseded after rollback to checkpoint 8. All raw
segments remain intact; the last occurrence in chronological continuation order
defines the committed trajectory. No new checkpoint selection is inferred.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
import math
from pathlib import Path
import statistics

from four_round_recovery_common import ROUNDS, CONTENT_ID, new_output, read_json, sha, write_json

METRICS = ['iou', 'dice', 'mean_boundary_distance_pitch_pct', 'hd95_pitch_pct',
           'area_error_pct', 'perimeter_error_pct', 'circularity_abs_error']

def table(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def committed_rows(segments, endpoint):
    committed = {}; superseded = []; raw_count = 0
    for path, rows in segments:
        for position, row in enumerate(rows, 2):
            epoch = int(row['epoch']); raw_count += 1
            for key, value in row.items():
                if value in [None, '']:
                    continue
                try:
                    number = float(value)
                except ValueError:
                    continue
                if not math.isfinite(number):
                    raise ValueError(f'Nonfinite value: {path}:{position}:{key}')
            record = {'source': path, 'line': position, 'values': row}
            if epoch in committed:
                superseded.append({'epoch': epoch, 'superseded': committed[epoch], 'committed': record})
            committed[epoch] = record
    if sorted(committed) != list(range(1, endpoint+1)):
        raise ValueError('Missing or unexpected committed epochs')
    return [committed[k] for k in sorted(committed)], superseded, raw_count

def close(actual, expected, context):
    if not math.isclose(float(actual), float(expected), rel_tol=1e-11, abs_tol=1e-12):
        raise ValueError(f'Historical number differs: {context}: {actual} versus {expected}')

def sem_summary(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row['method'], row['pillar_id'])].append(row)
    by_method = defaultdict(list)
    for (method, pillar), values in groups.items():
        if len(values) != 12 or len({r['exposure'] for r in values}) != 12:
            raise ValueError('SEM pillar is missing repeated exposures')
        by_method[method].append({key: statistics.median(float(r[key]) for r in values) for key in METRICS})
    result = {}
    for method, values in by_method.items():
        if len(values) != 36:
            raise ValueError('SEM comparison requires 36 independent physical pillars')
        result[method] = {f'median_{key}': statistics.median(r[key] for r in values) for key in METRICS}
    return result

def recover(root):
    result = {'schema': 1, 'status': 'PASS', 'historical_training_repeated': False,
              'checkpoint_selection_repeated': False, 'formal_baseline_changed': False, 'rounds': {}}
    for number, name in ROUNDS.items():
        folder = root/'Experiments'/name
        active = read_json(folder/'runs/active_run.json')
        design = read_json(folder/'config/experiment_design.json')
        if design['data']['source_content_sha256'] != CONTENT_ID or active['dataset_content_sha256'] != CONTENT_ID:
            raise ValueError('Different formal source bank')
        endpoint = 8 if number == 94 else 48
        if number == 94:
            if 'failed' not in active['status']:
                raise ValueError('R94 failure was lost')
        elif active['status'] != 'complete' or active['completed_epoch'] != 48:
            raise ValueError('Completed run identity changed')
        record_dir = folder/'runs'/('training_'+active['run_id'])
        paths = [record_dir/'training_log.csv']
        if number == 95:
            paths += [record_dir/f'training_log_continuation_{n:02d}.csv' for n in [1,2,3]]
        rows, superseded, raw_count = committed_rows([(p.relative_to(root).as_posix(), table(p)) for p in paths], endpoint)
        if bool(superseded) != (number == 95) or (number == 95 and [r['epoch'] for r in superseded] != [9]):
            raise ValueError('Unexpected rollback history')
        current = rows[-1]['values']; checks = 0
        final = active.get('final_validation', {})
        mapping = ({'val_detail_axis':'detail_axis','val_contour_axis':'contour_axis',
                    'val_identity_axis':'identity_axis','val_motion_axis':'motion_axis','val_worst_axis':'worst_axis'}
                   if number <= 95 else {'val_texture':'texture','val_contour':'contour',
                    'val_identity_gray':'identity_gray','val_motion':'motion','val_periodic_margin':'periodic_match_margin',
                    'val_wrong_pitch_rate':'periodic_wrong_pitch_rate'})
        if final:
            for column, key in mapping.items():
                close(current[column], final[key], f'R{number}:{column}'); checks += 1
        axes = [key for key in current if key.startswith('val_')]
        best = {}
        for key in axes:
            available = [(int(r['values']['epoch']), float(r['values'][key])) for r in rows if r['values'].get(key) not in ['',None]]
            if available:
                higher = 'margin' in key or 'separation' in key
                epoch, value = sorted(available, key=lambda pair: (-pair[1] if higher else pair[1], pair[0]))[0]
                best[key] = {'epoch': epoch, 'value': value, 'direction': 'higher' if higher else 'lower'}
        entry = {'run_id': active['run_id'], 'status': active['status'], 'planned_epochs': 48,
                 'committed_epochs': endpoint, 'raw_log_rows': raw_count, 'superseded_rows': superseded,
                 'log_sources': [{'path':p.relative_to(root).as_posix(),'sha256':sha(p)} for p in paths],
                 'final_recorded_validation': final, 'final_csv_numbers_checked': checks,
                 'best_observed_per_axis_without_reselection':best,
                 'same_run_continuation': active.get('same_run_continuation',False),
                 'segments': [{'path':p.relative_to(root).as_posix(),'rows':len(table(p))} for p in paths]}
        result['rounds'][str(number)] = entry
        if number in [97,98]:
            base = folder/'results/posttraining_validation'
            source = base/'sem_contour/results/tables'/('six_method_primary_contour_metrics.csv' if number==97 else 'primary_contour_metrics.csv')
            entry['sem_contour'] = sem_summary(table(source))
            entry['sem_unit'] = 'median over 12 exposures within each of 36 physical pillars, then median across pillars'
            if number==97:
                historical = read_json(base/'synthesis/summary.json')
                for method, values in entry['sem_contour'].items():
                    for key, value in values.items():
                        close(value,historical['sem_contour'][method][key], f'SEM:{method}:{key}');checks += 1
                appearance = table(base/'real_generalization/appearance_per_frame.csv')
                entry['real_appearance'] = {}
                for method, reference in historical['real_appearance'].items():
                    if method=='r97_vs_r96':continue
                    selected = [r for r in appearance if r['method']==method]
                    entry['real_appearance'][method] = {}
                    for key, expected in reference.items():
                        column = key.removeprefix('median_');value = statistics.median(float(r[column]) for r in selected)
                        close(value,expected,f'Appearance:{method}:{key}');checks += 1
                        entry['real_appearance'][method][key]=value
                motion = table(base/'real_generalization/motion_common_valid_summary.csv')
                entry['real_motion'] = {}
                for method, reference in historical['real_motion'].items():
                    if method.startswith('r97_minus'):continue
                    selected=[r for r in motion if r['method']==method];entry['real_motion'][method]={}
                    for key, expected in reference.items():
                        column=key.removeprefix('mean_sequence_');value=statistics.mean(float(r[column]) for r in selected)
                        close(value,expected,f'Motion:{method}:{key}');checks+=1
                        entry['real_motion'][method][key]=value
                entry['historical_summary_numbers_recomputed_and_checked']=checks
        print('NUMERIC_ROUND_REPLAYED',number,endpoint,checks,flush=True)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=new_output(args.root,args.output)
    report=recover(args.root)
    write_json(out/'REPLAYED_RESULTS.json',report)

if __name__=='__main__':main()
