"""Freeze a retrospective, matched normal-exposure comparison of saved masks."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import load, save, record, sha, now
import numpy as np
from scipy.io import loadmat, savemat


def main():
    out = ROOT / 'results/competitive_review'
    out.mkdir(parents=True, exist_ok=False)
    exps = ROOT.parent
    sources = {
        'R128_masks': ROOT / 'results/full_contour/masks.mat',
        'R128_measurements': ROOT / 'results/full_contour/measurements.csv',
        'R128_verification': ROOT / 'results/full_contour/verification.json',
        'historical_masks': exps / 'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/acm_arrays.mat',
        'historical_protocol': exps / 'R119_SequenceGeometryValidation/analysis/R109_comparison_20260907/protocol_v2.json',
        'R61_masks': exps / 'R69_ACMContourSEMValidation/results/masks/acm_primary_masks.mat',
        'R61_manifest': exps / 'R69_ACMContourSEMValidation/MANIFEST.md',
        'LSC_pairs': exps / 'R119_SequenceGeometryValidation/results/formal_lsc/analysis/tables/combined_lsc_per_pair.csv',
        'LSC_summary': exps / 'R119_SequenceGeometryValidation/results/formal_lsc/analysis/tables/combined_lsc_summary.csv',
        'LSC_metric_source': exps / 'R80_InflectionReferenceCircleSEMValidation/scripts/run_displacement_lsc.py',
        'metric_helper_source': ROOT / 'analysis/full_contour/run_contour_check.m',
        'prepare_source': Path(__file__),
        'worker_head': Path(__file__).with_name('worker_head.txt'),
    }
    verified = load(sources['R128_verification'])
    for key in ['masks', 'measurements']:
        assert sha(verified[key]['path']) == verified[key]['sha256']
    helper = sources['metric_helper_source'].read_text(encoding='utf-8')
    helper = helper[helper.index('function shifted = shift_binary'):]
    worker = Path(__file__).with_name('run_competitive_review.m')
    with worker.open('x', encoding='utf-8') as f:
        f.write(sources['worker_head'].read_text(encoding='utf-8') + '\n\n' + helper)
    sources['matlab_worker'] = worker
    plan = dict(
        created_utc=now(), retrospective=True,
        question='Do recent models improve matched real-pillar outer contour and circularity; what LSC evidence exists?',
        population='One existing paired SEM/optical specimen, same 36 pillars, repeated images 13/14/15. Not 108 independent specimens.',
        methods=['Raw', 'R61v16', 'R109_E48', 'R119_E42', 'R128_P_s1285002'],
        references=['historical', 'global_pitch_matched'],
        alignment='Same existing Raw-derived integer shift for every model in each pillar/exposure/reference; no independent model fitting.',
        segmentation='Reuse original primary masks (Chan-Vese 200 iterations, smoothness 1). Raw masks and SEM references must match exactly across source records.',
        summary='Median over the three exposures for each physical pillar, then median over 36 pillars; retain all exposure-specific and individual paired results. No significance or independent-specimen generalization claim.',
        metrics=['mean_boundary_px', 'hd95_px', 'iou', 'area_error_pct', 'perimeter_error_pct', 'circularity_error', 'maximum_boundary_px'],
        circularity='Absolute difference from actual fixed SEM circularity, not distance from a perfect circle.',
        LSC='Recompute historical summaries from same 120 Raw-locked pair records. R128 has no same-protocol LSC entry; do not substitute its Raw-relative registration result.',
        limits=['Existing development specimen and prior-selected models, no fresh confirmation.', 'R128 application includes its existing Raw-retention guard; also report the 16 fully neural interior pillars.', 'Fixed SEM references are not physical edge certification.', 'LSC step scatter is repeatability; nominal step deviation is not independent physical accuracy.', 'R119 causal-audit correction remains authoritative; V42 specific same-source training overlap limits inference.'],
        sources={k: record(v) for k, v in sources.items()},
    )
    save(out / 'plan.json', plan)
    new = loadmat(sources['R128_masks'], variable_names=['masks', 'truth_masks', 'shifts', 'opt_pitch', 'global_index'])
    old = loadmat(sources['historical_masks'], variable_names=['masks', 'truth_historical', 'truth_pitch_matched', 'opt_pitch'])
    r61 = loadmat(sources['R61_masks'], variable_names=['raw_masks', 'recon_masks', 'truth_masks', 'opt_pitch', 'global_index'])
    raw = new['masks'][:, :, :, :, 0, 0]
    assert np.array_equal(raw, old['masks'][:, :, :, :3, 0])
    assert np.array_equal(raw, r61['raw_masks'][:, :, :, :3])
    assert np.array_equal(new['truth_masks'][:, :, :, 0], old['truth_historical'])
    assert np.array_equal(new['truth_masks'][:, :, :, 1], old['truth_pitch_matched'])
    assert np.array_equal(new['truth_masks'][:, :, :, 0], r61['truth_masks'])
    assert np.array_equal(new['global_index'], r61['global_index'])
    assert np.array_equal(new['opt_pitch'], old['opt_pitch']) and np.array_equal(new['opt_pitch'], r61['opt_pitch'])
    masks = np.stack([raw, r61['recon_masks'][:, :, :, :3], old['masks'][:, :, :, :3, 1], old['masks'][:, :, :, :3, 4], new['masks'][:, :, :, :, 1, 0]], axis=-1)
    assert masks.shape == (104, 104, 36, 3, 5)
    savemat(out / 'inputs.mat', dict(masks=masks.astype(bool), truth_masks=new['truth_masks'].astype(bool), shifts=new['shifts'], opt_pitch=new['opt_pitch'], global_index=new['global_index']), do_compression=True)
    save(out / 'preparation.json', dict(verified_utc=now(), Raw_masks_exact_across_all_three_sources=True, historical_SEM_reference_exact=True, global_pitch_reference_exact=True, pitch_and_pillar_mapping_exact=True, sources_unchanged=all(sha(x['path']) == x['sha256'] for x in plan['sources'].values()), plan=record(out/'plan.json'), inputs=record(out/'inputs.mat')))
    print('Matched inputs verified and saved: 5 methods x 3 exposures x 36 pillars x 2 references.')


if __name__ == '__main__':
    main()
