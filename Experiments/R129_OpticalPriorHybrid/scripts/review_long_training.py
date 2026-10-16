"""Audit actual execution and independently recompute the fixed long-run results."""
import sys,json,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import load,sha,save,record,now,REPO
import numpy as np,pandas as pd,torch,cv2
from scipy.io import loadmat
from scipy.optimize import least_squares

def main():
    pkg=Path(load(ROOT/'config/standalone_build.json')['path']);run=pkg/'results/training/r129_long_01'
    out=ROOT/'results/long_training_review_20260913';out.mkdir(exist_ok=False)
    completion=load(run/'completion.json');cfg=load(pkg/'config/training.json')
    for item in completion['records']:assert sha(pkg/item['path'])==item['sha256']
    frozen=load(pkg/'PACKAGE_MANIFEST.json')
    for name,h in frozen['files'].items():assert sha(pkg/name)==h,name
    logs=sorted(run.glob('updates_*.jsonl'));rows=[json.loads(line) for f in logs for line in f.read_text().splitlines()]
    assert len(rows)==8192 and [r['step'] for r in rows]==list(range(1,8193))
    manifest=load(pkg/'training_data/manifest.json');entries={(e['split'],e['index']):e for e in manifest['entries']}
    for epoch in range(16):
        order=np.random.default_rng(np.random.SeedSequence([cfg['order_seed'],epoch])).permutation(512)
        subset=rows[epoch*512:(epoch+1)*512]
        assert len({r['parent_id'] for r in subset})==512
        for pos,r in enumerate(subset):
            e=entries[('train',int(order[pos]))]
            assert r['epoch']==epoch and r['position']==pos and r['parent_id']==e['parent_id'] and r['parent_arrays_sha256']==e['arrays_sha256']
            assert r['noise_seed']==[cfg['noise_seed'],epoch,int(order[pos])]
    sys.path.insert(0,str(pkg));from data import Bank
    bank=Bank();sample_steps=[]
    for epoch in range(16):
        for position in [0,127,255,511]:
            step=epoch*512+position+1;r=rows[step-1];index=int(bank.order(epoch)[position])
            b=bank.batch('train',index,'cpu',epoch)
            assert b['cpu_input_sha256']==r['actual_input_sha256'];sample_steps.append(step)
    final=torch.load(pkg/completion['final_checkpoint']['path'],map_location='cpu')
    assert final['step']==8192 and all(int(x['step'])==8192 for x in final['optimizer']['state'].values())
    from runtime import verify_binding,state_digest,create
    verify_binding(final['binding']);m,_=create('cpu');m.load_state_dict(final['model']);assert state_digest(m)==final['parameter_sha256']
    real_steps=cfg['real_steps'];summaries=[];tables=[];paired=[];motion=[];dev=[]
    for step in cfg['dev_steps']:
        d=load(run/f'evaluations/step{step:05d}/dev.json');assert len(d['rows'])==128
        assert abs(np.mean([r['loss'] for r in d['rows']])-d['mean_loss'])<1e-12
        dev.append(dict(step=step,loss=d['mean_loss']))
    for step in real_steps:
        folder=run/f'evaluations/step{step:05d}/real';d=load(folder/'complete.json')
        for im in d['images']:assert sha(pkg/im['image']['path'])==im['image']['sha256']
        table=pd.read_csv(folder/'sem_measurements.csv');assert len(table)==108 and not table.duplicated(['exposure','pillar']).any()
        table['step']=step;tables.append(table)
        metrics=['radial_nm','correlation','diameter_error_nm','MZC_error_nm','centered_shape_nm']
        by=table.groupby('pillar')[metrics].median();summary=by.median()
        assert all(abs(summary[k]-d['SEM'][k])<1e-10 for k in metrics)
        summaries.append(dict(step=step,**summary.to_dict(),**d['motion']))
        by['step']=step;paired.append(by.reset_index())
        centers=pd.read_csv(folder/'motion_centers.csv');panel=load(pkg/'validation/panel.json');reported=pd.read_csv(folder/'motion_pairs.csv').set_index('sequence')
        for pair in panel['motion_pairs']:
            s=panel['sequences'][pair['sequence']];g=centers[centers.sequence==pair['sequence']]
            a=g[g.frame_index==pair['start']].set_index('pillar_id');b=g[g.frame_index==pair['end']].set_index('pillar_id');assert len(a)==len(b)==9
            v=(b[['cx','cy']]-a[['cx','cy']]).to_numpy()*s['object_um_per_px'];dx,dy=np.median(v,axis=0)
            values=dict(nominal_error_nm=abs(abs(dx)-s['nominal_step_um'])*1000,within_grid_nm=np.std(v[:,0],ddof=1)*1000,cross_axis_nm=abs(dy)*1000)
            assert all(abs(value-reported.loc[pair['sequence'],k])<1e-8 for k,value in values.items())
            motion.append(dict(step=step,sequence=pair['sequence'],**values))
    pd.DataFrame(summaries).to_csv(out/'trajectory.csv',index=False);pd.DataFrame(dev).to_csv(out/'development.csv',index=False)
    all_tables=pd.concat(tables);all_tables.to_csv(out/'sem_measurements.csv',index=False)
    by=pd.concat(paired);by.to_csv(out/'per_pillar.csv',index=False);pd.DataFrame(motion).to_csv(out/'motion_pairs.csv',index=False)
    comparisons=[]
    for step in real_steps[1:]:
        a=by[by.step==step].set_index('pillar');b=by[by.step==0].set_index('pillar')
        for key in metrics:
            delta=a[key]-b[key];gain=delta if key=='correlation' else -delta
            comparisons.append(dict(step=step,metric=key,improved=int((gain>1e-7).sum()),worsened=int((gain< -1e-7).sum()),tied=int((abs(gain)<=1e-7).sum()),median_paired_change=float(delta.median())))
    pd.DataFrame(comparisons).to_csv(out/'paired_changes.csv',index=False)
    # Refit circles using independent two-coordinate optimization, eliminating radius analytically.
    def signature(points):
        def residual(c):
            r=np.linalg.norm(points-c,axis=1);return r-r.mean()
        c=least_squares(residual,points.mean(0),xtol=1e-12,ftol=1e-12,gtol=1e-12).x
        d=points-c;r=np.linalg.norm(d,axis=1);ang=np.mod(np.arctan2(d[:,1],d[:,0]),2*np.pi);order=np.argsort(ang);a=ang[order];v=r[order]
        sig=np.interp(np.arange(720)*2*np.pi/720,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[v[-1],v,v[0]])
        return sig,r.mean()
    scale=5000/float(loadmat(pkg/'validation/sem_reference.mat',variable_names=['opt_pitch'])['opt_pitch'].item())
    maximum=0.;signed=[]
    for step in real_steps:
        pts=np.load(run/f'evaluations/step{step:05d}/real/sem_points.npz');truth={i:signature(pts[f'SEM_{i}']) for i in range(1,37)}
        for r in all_tables[all_tables.step==step].itertuples():
            a,ra=signature(pts[f'{r.exposure}_{r.pillar}']);b,rb=truth[r.pillar]
            vals=[np.mean(abs(a-b))*scale,np.corrcoef(a,b)[0,1],2*abs(ra-rb)*scale,np.mean(abs((a-a.mean())-(b-b.mean())))*scale]
            expected=[r.radial_nm,r.correlation,r.diameter_error_nm,r.centered_shape_nm]
            maximum=max(maximum,max(abs(x-y) for x,y in zip(vals,expected)))
            signed.append(dict(step=step,exposure=r.exposure,pillar=r.pillar,radius_bias_nm=(ra-rb)*scale))
    assert maximum<.001
    pd.DataFrame(signed).to_csv(out/'signed_radius_bias.csv',index=False)
    replay=pkg/'results/inference/final_review_20260913/pillar_normal.png';saved=run/'evaluations/step08192/real/sem14.png'
    assert np.array_equal(cv2.imread(str(replay),0),cv2.imread(str(saved),0))
    result=dict(completed_utc=now(),source=record(__file__),package=str(pkg),completion=record(run/'completion.json'),completion_records_verified=len(completion['records']),immutable_package_files_verified=len(frozen['files']),unique_updates=8192,actual_update_rows=8192,each_epoch_all512_parents=True,independently_rebuilt_inputs=sample_steps,optimizer_step8192=True,scheduled_dev_evaluations=17,scheduled_real_evaluations=5,SEM_rows_independently_refitted=540,SEM_refit_max_difference=maximum,MZC_note='Historical shared algorithm, not independently reimplemented',motion_pairs_recomputed=20,final_public_inference_replay_exact=True,final_checkpoint=completion['final_checkpoint'],trajectory=summaries,paired_changes=comparisons,training_finished_utc=completion['completed_utc'],model_promoted=False,default_inference_unchanged=True)
    save(out/'verification.json',result)
    print(pd.DataFrame(summaries).to_string(index=False));print(pd.DataFrame(comparisons).query('step==8192').to_string(index=False))
if __name__=='__main__':main()
