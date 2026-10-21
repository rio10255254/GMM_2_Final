"""Read-only model and data diagnostics. Never trains or saves model weights.

Outputs are local diagnostic evidence, not new validation holdouts. This script
tests causal mechanisms and verifies the implemented meaning of training terms.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from model.r117_model import build_model, gradients, warp_local
from training.dataset import R117Dataset, known_width_gain
from training.losses import edge_center_coordinate, geometry_terms, paired_loss, soft_object, width_loss, detail_loss
from training.train import flatten, set_trainable
from torch.utils.data._utils.collate import default_collate

CONFIG = json.loads((ROOT / 'config/experiment.json').read_text(encoding='utf-8'))
RUN = ROOT / 'runs/r117_formal_scratch_20260905_004452'
WEIGHT = RUN / 'weights/epoch_042.pth'
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def stats(values):
    a = np.asarray(values, dtype=float)
    return {'n':int(a.size), 'mean':float(a.mean()), 'median':float(np.median(a)),
            'p05':float(np.percentile(a, 5)), 'p95':float(np.percentile(a, 95)), 'max':float(a.max())}

def tensor(a):
    return torch.as_tensor(a, dtype=torch.float32, device=DEVICE)[None,None]

def clean_json(x):
    if isinstance(x, dict): return {k:clean_json(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [clean_json(v) for v in x]
    if isinstance(x, (np.integer,np.floating)): return x.item()
    return x

def data_mass_audit():
    package = ROOT / CONFIG['data']['package_root']
    manifest = json.loads((package/'manifest.json').read_text())
    rows = [r for r in manifest['records'] if r['split']=='train']
    roles, families, polarity = Counter(), Counter(), Counter()
    mass, area = defaultdict(float), defaultdict(float)
    for row in rows:
        roles[row['role']] += 1; families[row['family']] += 1
        if row['role'] != 'flat_negative': polarity[str(row['polarity'])] += 1
        sdf = np.load(package/row['sdf_a']).astype(np.float32)
        # Match actual detector loss, which clamps before making its band.
        band = np.exp(-np.abs(np.clip(sdf,-12,12))/3.0)
        mass[row['family']] += float(band.sum())
        area[row['family']] += float((np.abs(sdf)<2.5).sum())
    total = sum(mass.values())
    return {
        'scene_count':len(rows), 'roles':dict(roles), 'families':dict(families), 'polarity':dict(polarity),
        'effective_identity_view_fraction':(len(rows)+2*roles['identity'])/(3*len(rows)),
        'dense_scene_fraction':families['dense_array']/len(rows),
        'dense_sdf_loss_weight_fraction':mass['dense_array']/total,
        'dense_boundary_pixel_fraction':area['dense_array']/sum(area.values()),
        'clamped_far_field_sdf_weight':math.exp(-12/3),
        'clamped_flat_boundary_target':math.exp(-12/2.5),
        'all_effective_target_views':len(rows)*3,
    }

def analytic_audit(model):
    # Positive SDF means foreground. Optical intensity normals reverse for dark foreground.
    coordinate = torch.arange(97, device=DEVICE, dtype=torch.float32)-48
    sdf = coordinate[None,None,None].expand(1,1,49,-1)
    ny = torch.zeros_like(sdf)
    values=[]
    for polarity in (1,-1):
        nx = torch.ones_like(sdf)*polarity
        locations = coordinate[None,None,None].expand_as(sdf)-sdf*nx
        valid = (sdf.abs()>=1)&(sdf.abs()<=6)
        reflection = coordinate[None,None,None].expand_as(sdf)-2*sdf*nx
        expected_reflection = -coordinate[None,None,None].expand_as(sdf)
        values.append({'polarity':polarity,
            'center_sampling_error_px':float(locations[valid].abs().mean()),
            'reflection_sampling_error_px':float((reflection-expected_reflection)[valid].abs().mean()),
            'sampling_center_from_x_4':float(locations[0,0,24,52]),
            'reflection_of_x_4':float(reflection[0,0,24,52])})

    # Native formula: the gain==1 correction has a discontinuity when the
    # original pixel lies outside the two endpoint samples.
    raw=torch.tensor([0.65], device=DEVICE)
    midpoint=torch.tensor([0.4], device=DEVICE); half=torch.tensor([0.1], device=DEVICE)
    jumps=[]
    for gain_value in (1.0,1.000001,1.001,1.01):
        gain=raw.new_tensor(gain_value)
        unit=((raw-midpoint)/half).clamp(-0.995,0.995)
        transformed=midpoint+half*torch.tanh(gain*torch.atanh(unit))
        transformed=transformed+(gain==1).to(transformed.dtype)*(raw-transformed).detach()
        proposal=raw+0.4*(transformed-raw)
        jumps.append({'gain':gain_value, 'change_gray':float((proposal-raw).item()*255)})

    # One whole-object normal-distance average is not an x,y position detector.
    yy,xx=np.mgrid[0:192,0:192].astype(np.float32)
    sdf_a=45-np.sqrt((xx-95.5)**2+(yy-95.5)**2)
    target=1/(1+np.exp(-np.clip(sdf_a/1.5,-30,30)))
    coord_target=float(edge_center_coordinate(tensor(target),tensor(sdf_a)))
    translations=[]
    for dx,dy in ((0,0),(0.5,0),(1,0),(2,0),(0,1),(1,1)):
        moved_sdf=45-np.sqrt((xx-95.5-dx)**2+(yy-95.5-dy)**2)
        moved=1/(1+np.exp(-np.clip(moved_sdf/1.5,-30,30)))
        score=float(edge_center_coordinate(tensor(moved),tensor(sdf_a)))
        translations.append({'true_center_shift_px':math.hypot(dx,dy),'dx':dx,'dy':dy,'reported_center_lock_error':abs(score-coord_target)})

    # Known logistic-width label treats scale as a Gaussian standard deviation.
    width=1.0; sigma=2.0
    # Logistic derivative variance is pi^2*s^2/3. Gaussian convolution adds sigma^2.
    widths={'target_logistic_scale_px':width,'gaussian_sigma_px':sigma,
            'implemented_gain':math.sqrt(width*width+sigma*sigma)/width,
            'variance_matched_logistic_gain':math.sqrt(width*width+3*sigma*sigma/(math.pi**2))/width,
            'interpretation':'variance-matched comparison is analytic, not an exact inverse of convolution'}
    # Repeated high-pass operations have zero DC only. They suppress mid-band
    # corrections and have negative sidelobes; they do not prohibit rings.
    frequencies=[]
    for wavelength in (4,8,16,32,64):
        lp=math.exp(-2*math.pi**2*3.2**2/wavelength**2)
        frequencies.append({'wavelength_px':wavelength,'three_highpass_small_signal_transmission':(1-lp)**3})
    return {'polarity_center_reflection':values, 'width_identity_discontinuity':jumps,
            'centroid_metric_blindness':translations,'known_width_scale_mismatch':widths,
            'repeated_highpass_approximation':frequencies}

@torch.inference_mode()
def forward_data_audit(model):
    dataset=R117Dataset('validation',epoch=0,role_filter='degraded')
    selected=[]
    for family in sorted(set(r['family'] for r in dataset.records)):
        for polarity in (1,-1):
            choices=[i for i,r in enumerate(dataset.records) if r['family']==family and r['polarity']==polarity]
            selected.extend(choices[:3])
    rows=[]; rng=np.random.default_rng(117505)
    for done,index in enumerate(selected,1):
        item=dataset[index]
        x=item['source'][:2].to(DEVICE); target=item['target'][:2].to(DEVICE); gt=item['sdf'][:2].to(DEVICE)
        d=model.forward_details(x)
        nxg,nyg=gradients(gt)
        ng=torch.sqrt(nxg.square()+nyg.square()+1e-8); nxg,nyg=nxg/ng,nyg/ng
        dot=nxg*d.normal_x+nyg*d.normal_y
        edge=(gt.abs()<4)&(gt.abs()>0.5)
        edge[..., :20,:]=False; edge[..., -20:,:]=False; edge[...,:,:20]=False; edge[...,:,-20:]=False
        original_center_flow=torch.cat((-gt*d.normal_x,-gt*d.normal_y),1)
        corrected_nx=d.normal_x*torch.where(dot<0,-1.0,1.0)
        corrected_ny=d.normal_y*torch.where(dot<0,-1.0,1.0)
        corrected_flow=torch.cat((-gt*corrected_nx,-gt*corrected_ny),1)
        center_error=warp_local(gt,original_center_flow).abs()
        corrected_error=warp_local(gt,corrected_flow).abs()
        label=(gt[0,0].abs()<2.5).cpu().numpy().flatten()
        score=d.boundary_confidence[0,0].cpu().numpy().flatten()
        sample=rng.choice(len(label), min(8192,len(label)), replace=False)
        auc=roc_auc_score(label[sample],score[sample]) if len(np.unique(label[sample]))>1 else 0.5
        output_grad=gradients(d.output); target_grad=gradients(target); source_grad=gradients(x)
        error_out=(output_grad[0]-target_grad[0]).abs()+(output_grad[1]-target_grad[1]).abs()
        error_raw=(source_grad[0]-target_grad[0]).abs()+(source_grad[1]-target_grad[1]).abs()
        mask=item['mask'][:2].to(DEVICE)
        midpoint=item['midpoint'][:2].to(DEVICE); polarity=item['polarity'][:2].to(DEVICE)
        target_soft=soft_object(target,midpoint,polarity)
        oracle_dice=(2*(target_soft*mask).flatten(1).sum(1)/(target_soft.flatten(1).sum(1)+mask.flatten(1).sum(1)+1e-6)).mean()
        # Detect actuator clipping: error above gain maximum attainable with a
        # frozen detector/source support, even with confidence=1 and amount=max.
        band=torch.exp(-d.predicted_sdf_px.abs()/3)
        support=d.source_support*d.boundary_confidence*(0.25+0.75*band)
        possible=1+2.5*support
        target_gain=item['known_width_gain'][:2].to(DEVICE)
        pair_shift=item['pair_shift_px']
        from training.losses import warp_translation
        shifted_gain=warp_translation(target_gain[:1],pair_shift[0:1].to(DEVICE),pair_shift[1:2].to(DEVICE))
        pair_band=torch.exp(-gt[1:2].abs()/3)
        width_inconsistency=((shifted_gain-target_gain[1:2]).abs()*pair_band).sum()/pair_band.sum()
        rows.append({
            'scene':int(item['scene_index']),'family':item['family'],'polarity':float(polarity[0]),'challenge':item['challenge'],
            'normal_wrong_sign_fraction':float((dot[edge]<0).float().mean()),
            'true_sdf_native_normal_sampling_error_px':float(center_error[edge].mean()),
            'true_sdf_sign_corrected_sampling_error_px':float(corrected_error[edge].mean()),
            'boundary_auc':float(auc), 'boundary_output_std':float(d.boundary_confidence.std()),
            'predicted_sdf_boundary_mae_px':float((d.predicted_sdf_px-gt).abs()[edge].mean()),
            'target_gain_beyond_actuator_fraction':float((target_gain[edge]>possible[edge]+0.05).float().mean()),
            'width_gate_edge_mean':float(d.width_gate[edge].mean()),
            'effective_width_gain_edge_mean':float(d.width_gain[edge].mean()),
            'target_width_gain_edge_mean':float(target_gain[edge].mean()),
            'perfect_known_width_pair_disagreement':float(width_inconsistency),
            'output_change_gray':float((d.output-x).abs().mean()*255),
            'output_mae_gray':float((d.output-target).abs().mean()*255),
            'raw_mae_gray':float((x-target).abs().mean()*255),
            'true_gradient_mae_raw':float(error_raw.mean()),'true_gradient_mae_output':float(error_out.mean()),
            'target_image_itself_soft_dice':float(oracle_dice),
        })
        if done%12==0: print(json.dumps({'forward_diagnostic_done':done,'total':len(selected)}),flush=True)
    grouped={}
    for name,group in [('all',rows),('bright',[r for r in rows if r['polarity']>0]),('dark',[r for r in rows if r['polarity']<0])]:
        grouped[name]={k:stats([r[k] for r in group]) for k in rows[0] if k not in {'scene','family','polarity','challenge'}}
    return {'population':'up to 3 scenes per family and polarity; same historical development validation', 'rows':rows,'summary':grouped}

def training_gradient_audit(model):
    dataset=R117Dataset('train',epoch=22,limit=12)
    batch=flatten(default_collate([dataset[i] for i in (0,1,2,3)]),DEVICE)
    results=[]
    for group in ('width','shift','detail'):
        params=set_trainable(model,group)
        d=model.forward_details(batch['source'])
        pair_total,terms=paired_loss(d,batch,batch['scenes'],CONFIG['training']['loss_weights'])
        rec={key:{'value':float(value.detach()),'requires_grad':value.requires_grad} for key,value in terms.items()}
        for key,value in terms.items():
            if value.requires_grad:
                grads=torch.autograd.grad(value,params,retain_graph=True,allow_unused=True)
                norm=math.sqrt(sum(float(g.detach().float().square().sum()) for g in grads if g is not None))
            else: norm=0.0
            rec[key]['active_group_gradient_norm']=norm
        results.append({'active_group':group,'terms':rec})
        del d,terms,pair_total
    set_trainable(model,'detail')
    d=model.forward_details(batch['source']); weights=CONFIG['training']['loss_weights']
    _,terms=detail_loss(d,batch,weights)
    return {'pair_terms':results,
            'detail_stage_contour_term_logged_but_not_in_total':('contour' in terms),
            'detail_stage_sdf_trainable':any(p.requires_grad for p in model.parameter_groups()['detector']),
            'detail_stage_uses_pair_training':False,
            'note':'Gradient checks use frozen final weights with temporary in-memory requires_grad flags. No optimizer steps.'}

def checkpoint_invariance_audit():
    a=torch.load(RUN/'weights/epoch_006.pth',map_location='cpu',weights_only=False)['model']
    b=torch.load(WEIGHT,map_location='cpu',weights_only=False)['model']
    detector_names=[k for k in a if k.startswith(('detector.','boundary_head.','sdf_head.','subpixel_refiner.'))]
    return {'detector_tensors':len(detector_names),'all_detector_tensors_bit_identical_E6_E42':all(torch.equal(a[k],b[k]) for k in detector_names)}

def run():
    started=time.time(); torch.manual_seed(117505); np.random.seed(117505); cv2.setNumThreads(1); torch.set_num_threads(4)
    protected=[WEIGHT,ROOT/'model/r117_model.py',ROOT/'training/train.py',ROOT/'training/losses.py',ROOT/'data/package/manifest.json']
    before={str(p):sha(p) for p in protected}
    saved=torch.load(WEIGHT,map_location='cpu',weights_only=False)
    model=build_model().to(DEVICE).eval(); model.load_state_dict(saved['model'],strict=True); model.requires_grad_(False)
    result={'status':'complete','device':str(DEVICE),'checkpoint':str(WEIGHT),'checkpoint_sha256':before[str(WEIGHT)],
        'corpus':data_mass_audit(), 'analytic':analytic_audit(model),
        'model_data':forward_data_audit(model),'gradients':training_gradient_audit(model),
        'checkpoint_freezing':checkpoint_invariance_audit()}
    result['protected_files_unchanged']=all(sha(p)==before[str(p)] for p in protected)
    result['elapsed_seconds']=time.time()-started
    (HERE/'audit_results.json').write_text(json.dumps(clean_json(result),indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='model_data'},indent=2),flush=True)
    print(json.dumps({'model_data_summary':result['model_data']['summary']},indent=2),flush=True)
    return 0

if __name__=='__main__': raise SystemExit(run())
