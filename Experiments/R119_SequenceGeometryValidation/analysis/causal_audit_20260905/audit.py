"""Read-only numerical investigation of R119 claims and execution deviations.

Writes only new diagnostics under this analysis directory. Never trains, edits
old results, refreshes receipts, or evaluates a new candidate on confirmation.
"""
from __future__ import annotations
import csv
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

OUT = Path(__file__).resolve().parent
W = OUT.parents[1]
B = W.parent / 'R118_PhysicalCoordinateRepairScratch'
sys.path.insert(0, str(W))
sys.path.insert(0, str(W / 'validation'))
from training.r119_dataset import R119Scenes, ASYM
from model.network import continuous_width
from model.ops import warp_local
from inference.run import load, read
from validation.sequence_metrics import estimate_position, summarize_sequence


def js(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for b in iter(lambda: stream.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def save(name, obj):
    path = OUT / name
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, indent=2, ensure_ascii=False, allow_nan=False)
def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec); sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def metadata_audit():
    records = js(B / 'data/package/manifest.json')['records']
    train = [r for r in records if r['split'] == 'train']
    neg = [r for r in train if r['polarity'] < 0]
    ds = R119Scenes('train', 1, 512, 'A', 1196001)
    sign_rows = []
    for index, record in enumerate(ds.records):
        if record['polarity'] < 0 and record['role'] != 'flat_negative':
            batch = ds[index]
            original = np.load(B / 'data/package' / record['sdf_a']).astype(np.float32)
            sign_rows.append({'scene': record['scene_index'], 'polarity': record['polarity'],
                             'max_abs_new_plus_original': float(np.max(np.abs(batch['sdf'][0,0].numpy() + original))),
                             'max_abs_new_minus_original': float(np.max(np.abs(batch['sdf'][0,0].numpy() - original)))})
            if len(sign_rows) == 6: break
    va = R119Scenes('validation', 0, 96, 'A', 1196001)
    vb = R119Scenes('validation', 0, 96, 'B', 1196001)
    differences = []
    for i in range(96):
        a, b = va[i], vb[i]
        differences.append({'source_mean_gray': float((a['source']-b['source']).abs().mean()*255),
                            'target_mean_gray': float((a['target']-b['target']).abs().mean()*255)})
    gy, gx = np.indices(ASYM.shape)
    centroid = [float(np.sum(ASYM*(gx-8))), float(np.sum(ASYM*(gy-8)))]
    impulse = np.zeros((65,65), np.float32); impulse[32,32] = 1
    response = cv2.filter2D(impulse, -1, ASYM)
    ry, rx = np.indices(response.shape)
    measured = [float(np.sum(response*(rx-32))), float(np.sum(response*(ry-32)))]
    bank = js(W / 'data/development_sequences/manifest.json')
    replay = module(W / 'data/build_sequence_bank.py', 'bank_audit_import')
    records_by_id = {r['scene_index']: r for r in records}
    replay_rows = []
    # Verify only existing dev observations. This does not regenerate the bank.
    for item in bank['records'][:91]:
        r = records_by_id[int(item['scene_id'].split('_')[1])]
        src = np.load(B/'data/package'/r['source_a']).astype(np.float32)
        value, _ = replay.observation(src, item['true_x_px'], item['true_y_px'], item['exposure_gain'],
                                     replay.kernel(item['kernel_id']), np.random.default_rng(item['noise_seed']))
        actual = np.load(W/item['source'])['source']
        replay_rows.append({'protocol': item['protocol'], 'max_gray_difference': int(np.max(np.abs(np.rint(value*255).astype(np.int16)-actual.astype(np.int16))))})
    return {'train_scenes': len(train), 'negative_polarity_scenes': len(neg),
            'negative_polarity_fraction': len(neg)/len(train), 'role_counts': dict(Counter(r['role'] for r in train)),
            'train_view_psf_different_count': sum(r['psf_a'] != r['psf_b'] for r in train),
            'signed_distance_reversal_fixtures': sign_rows,
            'A_B_validation_source_difference_gray_mean': float(np.mean([r['source_mean_gray'] for r in differences])),
            'A_B_validation_target_difference_gray_mean': float(np.mean([r['target_mean_gray'] for r in differences])),
            'A_B_changed_validation_records': sum(r['source_mean_gray'] > 0 for r in differences),
            'D_kernel_centroid_px': centroid, 'D_filter_impulse_shift_px': measured,
            'bank_first_scene_replay_max_gray': max(r['max_gray_difference'] for r in replay_rows),
            'bank_first_scene_replay_failures': sum(r['max_gray_difference'] != 0 for r in replay_rows),
            'bank_generation_is_native_bilinear_shift': True,
            'B_actual_change': 'shared gain/offset/noise sigma, unchanged stored a/b sources with different PSFs',
            'D_actual_change': 'A plus post-sampling asymmetric correlation; not B plus new optics',
            'enrichment_manifests_used_by_trainer': False}


def locator_audit():
    calibration = module(W/'validation/calibrate_locators.py', 'locator_calibration_audit')
    result = calibration.run()
    correct_reporting = []
    # Use only saved already-consumed confirmation position outputs; no new inference.
    saved_rows = [json.loads(line) for line in (W/'results/confirmation/per_scene.jsonl').read_text().splitlines()]
    for key in ('raw_a_position','model_a_position','raw_b_position','model_b_position'):
        positions = [np.asarray(r[key], float) for r in saved_rows if r.get(key) is not None]
        error = np.linalg.norm(positions, axis=1)
        correct_reporting.append({'readout': key, 'correct_reference_error_is_zero_px': True,
            'valid': len(positions), 'invalid': 144-len(positions), 'median_error_px': float(np.median(error)),
            'p95_error_px': float(np.percentile(error,95)), 'max_error_px': float(np.max(error))})
    # Test the advertised grouping rule with two constant biases from two scenes.
    mixed = [{'scene_id': s, 'condition_id':'c', 'protocol':'static_repeat', 'frame_index':k,
              'valid':True, 'estimated_x_px':bias, 'estimated_y_px':0, 'true_x_px':0, 'true_y_px':0}
             for s,bias in [('one',0),('two',10)] for k in range(3)]
    accepted = summarize_sequence(mixed)
    # A one-direction image is not identifiable in the other direction.
    edge = np.repeat(np.linspace(0,1,128,dtype=np.float32)[None],128,axis=0)
    rank = asdict(estimate_position(edge, edge))
    return {'calibration_reported_status': result['status'],
            'gain_bias_fixture': result['controls']['gain_bias_only'],
            'gain_bias_fixture_enforced_in_pass': False,
            'mixed_scenes_wrongly_accepted_repeat_sd_px': accepted['repeat_sd_x_px'],
            'rank_deficient_fixture': rank,
            'confirmation_corrected_saved_position_summaries': correct_reporting,
            'confirmation_scope': 'analysis of existing consumed results; no new candidate, no tuning',
            'confirmation_original_error': 'subtracting shift_xy again from fits already relative to each corresponding shifted target'}


def table_reanalysis():
    rows = []
    for tag, folder in [('probe_B','shortlist_sem_B'),('E24','formal_E024_sem'),('E36','formal_E036_sem'),('E42','formal_sem')]:
        frame = pd.read_csv(W/f'results/{folder}/results/tables/primary_contour_metrics.csv')
        method = next(x for x in frame.method.unique() if x != 'Raw')
        pair = frame.pivot(index=['pillar_id','exposure'],columns='method',values='mean_boundary_distance_pitch_pct')
        effect = (pair[method]-pair.Raw).groupby('pillar_id').median()
        rng = np.random.default_rng(1199001)
        samples = np.median(rng.choice(effect.to_numpy(), (2000,len(effect)),replace=True),axis=1)
        rows.append({'model':tag,'pillar_n':len(effect), 'candidate_minus_Raw_pitch_percentage_points':float(effect.median()),
            'pillar_bootstrap95':np.percentile(samples,[2.5,97.5]).tolist(),
            'improved_pillars':int((effect<0).sum()),
            'candidate_area_error_median_pct':float(frame[frame.method==method].area_error_pct.median()),
            'Raw_area_error_median_pct':float(frame[frame.method=='Raw'].area_error_pct.median()),
            'candidate_perimeter_error_median_pct':float(frame[frame.method==method].perimeter_error_pct.median())})
    acm = []
    for suite in ['R73','R74']:
        f = pd.read_csv(W/f'results/formal_acm/{suite}/locked_acm_contract/results/tables/primary_contour_metrics.csv')
        for alignment, group in f.groupby('alignment'):
            p = group.pivot(index='image_id',columns='method',values='mean_boundary_distance_px')
            method = next(x for x in p if x != 'Raw'); d = p[method]-p.Raw
            acm.append({'suite':suite,'alignment':alignment,'Raw_median_px':float(p.Raw.median()),
                'candidate_median_px':float(p[method].median()),'paired_median_change_px':float(d.median()),
                'improved_images':int((d<0).sum()), 'worsened_images':int((d>0).sum()),
                'n':len(d)})
    lsc = pd.read_csv(W/'results/formal_lsc/analysis/tables/candidate_lsc_per_pair.csv')
    reference = pd.read_csv(W.parent/'R111_R109V42ThesisReplacementQualification/results/lsc_current_top30/tables/four_method_lsc_per_pair_current_top30.csv')
    lsc_rows = []
    for m,f in [('E42',lsc),('Raw',reference[reference.method=='Raw']),('R109',reference[reference.method=='R109 E48'])]:
        for sequence, group in f.groupby('sequence'):
            lsc_rows.append({'method':m,'sequence':sequence,'steps':len(group),
                'step_sd_nm':float(group.measured_step_um.std(ddof=1)*1000),
                'signed_step_bias_nm':float((group.measured_step_um-group.nominal_step_um).mean()*1000),
                'cross_axis_nm':float(group.cross_axis_abs_nm.median())})
    return {'SEM_pillar_paired_effects':rows,'ACM_alignment_reanalysis':acm,'LSC_by_sequence':lsc_rows,
            'historical_LSC_bootstrap_is_iid_steps_within_sequence': True,
            'historical_LSC_CI_not_block_aware': True}


@torch.inference_mode()
def common_inputs():
    ds = R119Scenes('validation', 0, 96, 'A', 1196001)
    entries = [ds[i] for i in range(len(ds))]
    x = torch.cat([e['source'] for e in entries]); target = torch.cat([e['target'] for e in entries])
    sdf = torch.cat([e['sdf'] for e in entries]); weights = .2+.8*torch.exp(-sdf.abs()/4)
    roles = [e['role'] for e in entries for _ in range(2)]
    sources_digest = hashlib.sha256(x.numpy().tobytes()).hexdigest()
    models = []
    for arm in ['A','B','D']:
        for seed in [1185001,1185002]:
            models.append((f'{arm}_s{seed}', W/f'runs/probe_{arm}_s{seed}/weights/epoch_012.pth'))
    models += [('R118_E12',B/'runs/verified_physical_repair/weights/epoch_012.pth')]
    models += [(f'formal_E{e}',W/f'runs/formal_B_s1195001/weights/epoch_{e:03d}.pth') for e in [24,36,42]]
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    metrics = []
    for name, checkpoint in [('Raw',None), *models]:
        model = load(checkpoint, device) if checkpoint else None
        for start in range(0,len(x),8):
            raw = x[start:start+8].to(device); truth = target[start:start+8].to(device)
            if model is None: output = raw
            else: output = model(raw)
            residual = output-truth
            mae = residual.abs().mean((1,2,3))*255
            grad = ((residual[...,1:]-residual[...,:-1]).abs().mean((1,2,3))+
                    (residual[...,1:,:]-residual[...,:-1,:]).abs().mean((1,2,3)))
            band = weights[start:start+len(raw)].to(device)
            edge = (residual.abs()*band).sum((1,2,3))/band.sum((1,2,3))*255
            for j in range(len(raw)):
                metrics.append({'method':name,'view_index':start+j,'scene_index':ds.records[(start+j)//2]['scene_index'],
                    'role':roles[start+j], 'image_mae_gray':float(mae[j]),'gradient_error':float(grad[j]),
                    'edge_weighted_mae_gray':float(edge[j])})
        print(f'common_input_done {name}',flush=True)
        if model is not None: del model
    pd.DataFrame(metrics).to_csv(OUT/'common_inputs_per_view.csv',index=False)
    grouped = pd.DataFrame(metrics).groupby(['method','role'])[['image_mae_gray','gradient_error','edge_weighted_mae_gray']].mean().reset_index()
    grouped.to_csv(OUT/'common_inputs_by_role.csv',index=False)
    all_stats = pd.DataFrame(metrics).groupby('method')[['image_mae_gray','gradient_error']].mean().reset_index()
    return {'population':'fixed first 96 existing development scenes, 192 identical views for every method',
            'source_tensor_sha256':sources_digest,'role_counts_scenes':dict(Counter(e['role'] for e in entries)),
            'all_view_means':all_stats.to_dict('records'),'per_role':grouped.to_dict('records')}


@torch.inference_mode()
def path_checks():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    ds = R119Scenes('validation',0,12,'A',1196001)
    x = torch.cat([ds[i]['source'] for i in range(12)])
    target = torch.cat([ds[i]['target'] for i in range(12)])
    results = []
    checkpoints = [('R118_E12', B/'runs/verified_physical_repair/weights/epoch_012.pth'),
                   ('R119_E42', W/'runs/formal_B_s1195001/weights/epoch_042.pth')]
    for name, ckpt in checkpoints:
        model = load(ckpt,device)
        for start in range(0,len(x),4):
            raw, truth = x[start:start+4].to(device), target[start:start+4].to(device)
            d = model.forward_details(raw)
            anchor = warp_local(raw,d.flow)
            real_no_detail = d.geometry_output.clamp(0,1)
            neutral = (anchor+d.detail).clamp(0,1)
            old_labeled_no_detail = anchor.clamp(0,1)
            true_no_shift = (continuous_width(raw,d.width_gain,d.sdf,d.normals,model.config['local_range_window'])+d.detail).clamp(0,1)
            for variant, output in [('base',d.output),('no_detail_only',real_no_detail),('no_width_only',neutral),
                                    ('old_labeled_no_detail',old_labeled_no_detail),('no_shift_only',true_no_shift)]:
                results.append({'model':name,'batch':start,'variant':variant,
                    'image_mae_gray':float((output-truth).abs().mean()*255),
                    'output_change_gray':float((output-raw).abs().mean()*255),
                    'norm_to_base_gray':float((output-d.output).abs().mean()*255)})
            if start == 0:
                diff = (real_no_detail-old_labeled_no_detail).abs()
                results.append({'model':name,'batch':start,'variant':'old_vs_correct_no_detail_difference',
                    'max_gray':float(diff.max()*255),'mean_gray':float(diff.mean()*255)})
        del model
    return {'rows':results,'scope':'24 fixed existing development views; diagnostic forward interventions, no weight update',
            'old_no_detail_also_disabled_width':True, 'corrected_no_detail_keeps_width':True}


def main():
    torch.set_num_threads(4); cv2.setNumThreads(1)
    protected = [W/'training/r119_dataset.py', W/'training/train_r119.py',W/'model/network.py',
                 W/'results/design_decision.json', W/'results/confirmation/consumption.json',
                 W/'runs/formal_B_s1195001/weights/epoch_042.pth',B/'data/package/manifest.json',
                 B/'data/confirmation/manifest.json']
    before = {str(p):sha(p) for p in protected}
    result = {'created_at_utc':datetime.now(timezone.utc).isoformat(), 'scope':'diagnosis only; no training/model/data mutation',
              'metadata':metadata_audit(),'locator':locator_audit(),'existing_table_reanalysis':table_reanalysis()}
    save('audit_metadata.json',result)
    result['common_input_comparison'] = common_inputs()
    result['correct_path_diagnostic'] = path_checks()
    after = {str(p):sha(p) for p in protected}
    assert before == after, 'Protected artifact changed during diagnostic'
    result['protected_before_after_sha256'] = before
    save('audit_results.json',result)
    print(json.dumps({'status':'diagnostics_complete','protected_unchanged':True,'output':str(OUT/'audit_results.json')},indent=2))


if __name__ == '__main__':main()
