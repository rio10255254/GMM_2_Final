"""Rebuild consumed inputs, recompute metrics and replay the saved candidate."""
import os, sys, json, importlib.util
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'scripts')]
from common import *
import numpy as np
import pandas as pd
import torch, cv2
from scipy.io import loadmat
from scipy.optimize import least_squares
from run_pilot import setup
from model.hybrid_v2 import Hybrid
from evaluate_real import guard

def main():
    plan = load(ROOT/'config/plan.json')
    checked = []
    def verify_records(obj):
        if isinstance(obj, dict):
            if 'path' in obj and 'sha256' in obj:
                assert sha(obj['path']) == obj['sha256'], obj['path']
                checked.append(obj['path'])
            for value in obj.values(): verify_records(value)
        elif isinstance(obj, list):
            for value in obj: verify_records(value)
    for name in ['config/plan.json','config/implementation_v2.json','data/PSF_PROVENANCE.json',
                 'runs/pilot_started.json','results/pilot_training.json','results/real_inference.json']:
        verify_records(load(ROOT/name))
    setup(plan['common_seed'])
    ledgers = {}
    states = {}
    changes = {}
    for arm in plan['arms']:
        rows = [json.loads(line) for line in (ROOT/f'runs/{arm}/updates.jsonl').read_text().splitlines()]
        assert [r['update'] for r in rows] == list(range(1,25))
        ledgers[arm] = rows
        first = torch.load(ROOT/f'runs/{arm}/initial.pth',map_location='cpu')
        last = torch.load(ROOT/f'runs/{arm}/step24.pth',map_location='cpu')
        assert first['step']==0 and last['step']==24 and last['arm']==arm
        assert all(int(v['step']) == 24 for v in last['optimizer']['state'].values())
        states[arm] = first['model']
        changes[arm] = {k:float((v-first['model'][k]).abs().max()) for k,v in last['model'].items()}
        assert max(changes[arm].values()) > 0
    for arm in 'BCD':
        assert all(torch.equal(v,states[arm][k]) for k,v in states['A'].items())
        for a,b in zip(ledgers['A'],ledgers[arm]):
            for key in ['parent_id','actual_input_sha256','source_arrays_sha256','noise_seed']:
                assert a[key] == b[key]
    spec=importlib.util.spec_from_file_location('r129_audit_data',R128/'training/data.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    bank=module.Bank()
    for index,row in zip(plan['train_indices'],ledgers['A']):
        batch=bank.batch('train',index,'cpu',epoch=0)
        assert batch['cpu_input_sha256'] == row['actual_input_sha256']
        assert batch['metadata']['parent_id'] == row['parent_id']
    print('All 96 updates and 24 rebuilt inputs reconciled',flush=True)

    # A separate two-parameter circle fit eliminates radius analytically.
    def signature(points):
        def residual(c):
            r=np.linalg.norm(points-c,axis=1);return r-r.mean()
        center=least_squares(residual,points.mean(0),xtol=1e-12,ftol=1e-12,gtol=1e-12).x
        delta=points-center; angles=np.mod(np.arctan2(delta[:,1],delta[:,0]),2*np.pi)
        radii=np.linalg.norm(delta,axis=1)
        order=np.argsort(angles); a=angles[order]; r=radii[order]
        sig=np.interp(np.arange(720)*2*np.pi/720,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[r[-1],r,r[0]])
        return sig,radii.mean()
    pts=np.load(ROOT/'results/sem/boundary_points.npz')
    rows=pd.read_csv(ROOT/'results/sem/per_measurement.csv')
    assert len(rows)==864 and not rows.duplicated(['tag','exposure','pillar']).any()
    scale=5000/float(loadmat(ROOT.parent/'R70_V42ACMContourSEMValidation/results/masks/acm_primary_masks.mat',variable_names=['opt_pitch'])['opt_pitch'].item())
    truths={i:signature(pts[f'SEM_{i}']) for i in range(1,37)}
    maxdiff={k:0. for k in ['radial_nm','correlation','diameter_error_nm','centered_shape_nm']}
    for row in rows.itertuples():
        a,ra=signature(pts[f'{row.tag}_{row.exposure}_{row.pillar}']);b,rb=truths[row.pillar]
        recomputed=[np.mean(abs(a-b))*scale,np.corrcoef(a,b)[0,1],2*abs(ra-rb)*scale,np.mean(abs((a-a.mean())-(b-b.mean())))*scale]
        for key,value in zip(maxdiff,recomputed): maxdiff[key]=max(maxdiff[key],abs(value-getattr(row,key)))
    assert max(maxdiff.values()) < .001, maxdiff
    print('All 864 fine-contour rows independently refitted',flush=True)

    centers=pd.read_csv(ROOT/'results/motion_centers_with_raw.csv')
    expected=pd.read_csv(ROOT/'results/motion_pairs.csv')
    panel=load(ROOT/'config/real_panel.json');cfg=load(panel['sequence_config']['path'])
    max_motion=0.
    for r in expected.itertuples():
        g=centers[(centers.tag==r.tag)&(centers.sequence==r.sequence)]
        a=g[g.frame_index==r.start].set_index('pillar_id');b=g[g.frame_index==r.end].set_index('pillar_id')
        assert len(a)==len(b)==9
        v=(b[['cx','cy']]-a[['cx','cy']]).to_numpy()*cfg['sequences'][r.sequence]['object_um_per_px']
        values=[abs(abs(np.median(v[:,0]))-cfg['sequences'][r.sequence]['nominal_step_um'])*1000,np.std(v[:,0],ddof=1)*1000,abs(np.median(v[:,1]))*1000]
        max_motion=max(max_motion,max(abs(x-y) for x,y in zip(values,[r.nominal_error_nm,r.within_grid_nm,r.cross_axis_nm])))
    assert max_motion<1e-8

    kernels=np.load(ROOT/'data/measured_psf_bank.npz')
    m=Hybrid(torch.from_numpy(kernels['mean']),torch.from_numpy(kernels['candidates'])).cuda()
    m.load_state_dict(torch.load(ROOT/'runs/D/step24.pth',map_location='cuda')['model']);m.eval()
    raw=cv2.imread(panel['sem'][1]['source']['path'],0)
    x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].cuda()
    with torch.no_grad():
        details=m.forward_details(x,trace=True);out=guard(x,details.output)[0,0].cpu().numpy()
        assert np.array_equal(out,np.load(ROOT/'results/real/D_24/sem14.npz')['output'])
        m.optical_enabled=False;no_optics=guard(x,m(x))[0,0].cpu().numpy();m.optical_enabled=True
        m.prior.aa=False;no_aa=guard(x,m(x))[0,0].cpu().numpy();m.prior.aa=True
        for p in m.optics.gating.parameters():p.zero_()
        uniform=guard(x,m(x))[0,0].cpu().numpy()
    contribution=dict(optics_max_abs=float(abs(out-no_optics).max()),optics_mean_abs=float(abs(out-no_optics).mean()),AA_max_abs=float(abs(out-no_aa).max()),AA_mean_abs=float(abs(out-no_aa).mean()),learned_vs_uniform_gating_max_abs=float(abs(out-uniform).max()),learned_vs_uniform_gating_mean_abs=float(abs(out-uniform).mean()),alpha=float(details.optical['alpha']),beta=float(details.optical['beta']),weights=details.optical['weights'].cpu().tolist())
    assert contribution['optics_max_abs']>0 and contribution['AA_max_abs']>0
    save(ROOT/'results/verification.json',dict(completed_utc=now(),source=record(__file__),frozen_records_verified=len(set(checked)),verified_paths=sorted(set(checked)),identical_initial_tensors=True,identical_inputs=True,rebuilt_inputs=24,optimizer_updates=96,parameter_max_changes=changes,independent_SEM_rows=864,independent_SEM_max_difference=maxdiff,MZC_note='Uses historical shared optimizer; not independently reimplemented',motion_pairs_recomputed=len(expected),motion_max_difference_nm=max_motion,D_full_sem14_float_replay_exact=True,real_module_contribution=contribution,pilot_technical_checks_passed=True,scientific_improvement_or_novelty_not_established=True))
    print(json.dumps(contribution,indent=2))

if __name__=='__main__':main()
