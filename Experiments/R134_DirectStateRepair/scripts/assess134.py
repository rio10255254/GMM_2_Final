from pathlib import Path
import sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rt import *
import pandas as pd
from scipy.optimize import least_squares
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def fit(xy):
    origin=xy.mean(0);z=xy-origin
    def r(c):v=np.linalg.norm(z-c,axis=1);return v-v.mean()
    c=least_squares(r,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12).x
    return c+origin,np.linalg.norm(z-c,axis=1).mean()

def main():
    cfg=load(ROOT/'config/study.json');verify()
    while not (ROOT/'results/matrix_complete.json').exists() or not (ROOT/'results/real_complete.json').exists():time.sleep(5)
    reports=[];checks=[];allrows=[];states={};logs={};refits=[]
    for seed in cfg['seeds']:
        for arm in cfg['arms']:
            name=f'R134_{arm}_s{seed}';run=ROOT/'runs'/name;started=load(run/'started.json');assert started['cfg']['sha256']==sha(ROOT/'config/study.json')
            initial=torch.load(run/'initial.pth',map_location='cpu');final=torch.load(run/'step0512.pth',map_location='cpu');assert final['step']==512
            assert all(int(v['step'])==512 for v in final['optimizer']['state'].values())
            states[arm,seed]=initial['model'];rows=[json.loads(x) for x in (run/'updates.jsonl').read_text().splitlines()];assert [r['step'] for r in rows]==list(range(1,513)) and len({r['parent'] for r in rows})==512;logs[arm,seed]=rows
            # Independent actual input replay across the complete one-pass schedule.
            manifest=load(Path(PROJECT_ROOT / cfg['data_root'])/'manifest.json');entries={e['index']:e for e in manifest['entries'] if e['split']=='train'}
            for row in rows[::16]:
                index=row['parent'];entry=entries[index];data=np.load(Path(PROJECT_ROOT / cfg['data_root'])/entry['arrays_path']);meta=load(Path(PROJECT_ROOT / cfg['data_root'])/entry['metadata_path']);rng=np.random.default_rng(np.random.SeedSequence([cfg['noise_seed'],0,index]));image=np.rint(np.clip(data['noiseless'].astype(np.float64)+rng.normal(0,meta['noise_sigma_gray']/255,data['source'].shape),0,1)*255).astype(np.uint8);tensor=np.ascontiguousarray(image[:,None,32:352,32:352].astype(np.float32)/np.float32(255));assert digest(tensor)==row['input_sha256']
            dev=load(run/'dev_0512.json');clean=[r['mae_gray'] for r in dev['rows'] if r['category']=='clean_identity'];reports.append(dict(arm=arm,seed=seed,dev_mae_gray=dev['mean_mae_gray'],Raw_dev_mae_gray=dev['Raw_mae_gray'],clean_identity_mae_gray=float(np.mean(clean)),clean_max_gray=float(max(clean))))
            for step in [0,512]:
                folder=ROOT/f'results/real/{arm}_s{seed}_p{step:04d}';table=pd.read_csv(folder/'measurements.csv');assert len(table)==108;points=np.load(folder/'points.npz');scale=load(folder/'complete.json')['scale_nm_per_px']
                for row in table.itertuples():
                    c,r=fit(points[f'{row.exposure}_{row.pillar}']);tc,tr=fit(points[f'SEM_{row.pillar}']);err=abs(2*(r-tr)*scale-row.signed_diameter_nm);assert err<1e-4;refits.append(dict(arm=arm,seed=seed,step=step,pillar=row.pillar,exposure=row.exposure,error_nm=err))
                allrows.append(table)
        assert all(torch.equal(v,states['C',seed][k]) for k,v in states['A',seed].items())
        assert [r['input_sha256'] for r in logs['A',seed]]==[r['input_sha256'] for r in logs['C',seed]]
    assert [r['input_sha256'] for r in logs['A',cfg['seeds'][0]]]==[r['input_sha256'] for r in logs['A',cfg['seeds'][1]]]
    t=pd.concat(allrows,ignore_index=True);t.to_csv(ROOT/'results/all_SEM_measurements.csv',index=False);pd.DataFrame(reports).to_csv(ROOT/'results/development_summary.csv',index=False);pd.DataFrame(refits).to_csv(ROOT/'results/independent_SEM_refits.csv',index=False)
    for seed in cfg['seeds']:
        end=t[(t.seed==seed)&(t.step==512)];a=end[end.arm=='A'].set_index(['pillar','exposure']);c=end[end.arm=='C'].set_index(['pillar','exposure']);raw=t[(t.seed==seed)&(t.step==0)&(t.arm=='C')].set_index(['pillar','exposure'])
        improvements=[];pass_flags=[]
        for key in ['diameter_error_nm','centered_shape_nm']:
            delta=(c[key]-a[key]).groupby('pillar').median();reference=a[key].groupby('pillar').median().median();relative=float(delta.median()/reference);rawrelative=float((c[key]-raw[key]).groupby('pillar').median().median()/raw[key].groupby('pillar').median().median())
            checks.append(dict(seed=seed,metric=key,paired_relative_change_vsA=relative,paired_relative_change_vsRaw=rawrelative,vsA_noninferiority_pass=relative<=.02,vsRaw_noninferiority_pass=rawrelative<=.02));improvements.append(relative<=-.05);pass_flags.extend([relative<=.02,rawrelative<=.02])
        d=next(r for r in reports if r['arm']=='C' and r['seed']==seed);pass_flags.extend([any(improvements),d['dev_mae_gray']<d['Raw_dev_mae_gray'],d['clean_identity_mae_gray']<=1.]);checks.append(dict(seed=seed,stage1_pass=all(pass_flags),at_least_one_useful_SEM_gain=any(improvements),dev_learning_pass=d['dev_mae_gray']<d['Raw_dev_mae_gray'],clean_pass=d['clean_identity_mae_gray']<=1.))
    passes=all(x['stage1_pass'] for x in checks if 'stage1_pass' in x)
    selected=min((r for r in reports if r['arm']=='C'),key=lambda r:r['dev_mae_gray'])['seed'] if passes else None
    save(ROOT/'results/screening_decision.json',dict(utc=now(),A_C_complete=True,B_D_complete=False,B_D_reason='independent material/optical calibration not yet supplied or qualified',checks=checks,eligible_for_motion_stage=passes,selected_seed_by_dev_only=selected,eligible_for_long_training=False,long_training_reason='Motion qualification still required' if passes else 'Failed prospectively frozen SEM/learning criteria; do not package as long-worthy',independent_input_replays=128,independent_SEM_refits=len(refits),max_refit_difference_nm=max(r['error_nm'] for r in refits),source=record(__file__)))
    print(json.dumps(checks,ensure_ascii=False,indent=2));print('Motionstage eligibility',passes,flush=True)
if __name__=='__main__':main()
