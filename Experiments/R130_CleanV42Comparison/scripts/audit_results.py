"""Verify the full fresh V42 trajectory and recompute final real comparisons."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import pandas as pd,cv2
from scipy.optimize import least_squares
from scipy.io import loadmat
from data_bank import Bank
from continuous import reader
def main():
    out=ROOT/'results/audit';out.mkdir(exist_ok=False);run=ROOT/'runs/v42_clean';completion=load(run/'completion.json');continuous=load(ROOT/'results/continuous/complete.json');cfg=load(ROOT/'config/training.json');verify_frozen()
    assert completion['epochs']==32 and completion['updates']==4096 and continuous['frames']==201
    assert continuous['source']==load(ROOT/'results/continuous/started.json')['source']
    for rec in load(ROOT/'config/evaluation_implementation.json')['sources']:assert sha(rec['path'])==rec['sha256']
    recovery=load(ROOT/'results/io_recovery/recovery_plan.json')
    for name in ['wrapper','original_atomic_source','frozen_source_manifest']:
        rec=recovery[name];assert sha(rec['path'])==rec['sha256']
    for rec in completion['records']:assert sha(rec['path'])==rec['sha256']
    rows=[json.loads(line) for p in sorted(run.glob('updates_*.jsonl')) for line in p.read_text(encoding='utf-8').splitlines()];latest={};replays=[]
    for row in rows:
        if row['step'] in latest:
            old=latest[row['step']];assert row['parents']==old['parents'];delta=abs(row['loss']-old['loss']);assert delta<1e-6;replays.append(dict(step=row['step'],loss_difference=delta))
        latest[row['step']]=row
    assert set(latest)==set(range(1,4097));bank=Bank();rebuild=[]
    for epoch in range(32):
        order=bank.order(epoch);seen=[]
        for pos in range(128):
            row=latest[epoch*128+pos+1];assert row['epoch']==epoch and row['position']==pos
            ids=[p['index'] for p in row['parents']];assert ids==order[pos*4:(pos+1)*4].tolist();seen+=ids
            for p in row['parents']:
                e=bank.entries[('train',p['index'])];assert p['source_arrays_sha256']==e['arrays_sha256'] and p['parent_id']==e['parent_id'];assert p['noise_seed']==[cfg['noise_seed'],epoch,p['index']]
            if pos in [0,127]:
                b=bank.batch('train',ids,'cpu',epoch);assert b['ledger']==row['parents'];rebuild.append(row['step'])
        assert len(seen)==len(set(seen))==512
    fresh,_=create('cpu');initial=torch.load(run/'checkpoints/step00000.pth',map_location='cpu');assert digest(fresh)==initial['parameter_sha256']
    final=torch.load(completion['checkpoint']['path'],map_location='cpu');assert final['step']==4096 and final['binding']==sha(ROOT/'config/frozen.json')
    assert all(int(x['step'])==4096 for x in final['optimizer']['state'].values())
    fresh.load_state_dict(final['model']);assert digest(fresh)==final['parameter_sha256']
    trajectories=[];sem_tables=[]
    for epoch in cfg['validation_epochs']:
        d=run/'evaluations'/f'epoch{epoch:02d}'/'real';r=load(d/'complete.json');t=pd.read_csv(d/'sem_measurements.csv');assert len(t)==108 and not t.duplicated(['exposure','pillar']).any()
        metrics=['radial_nm','correlation','diameter_error_nm','MZC_error_nm','centered_shape_nm'];summary=t.groupby('pillar')[metrics].median().median().to_dict()
        assert all(abs(summary[k]-r['SEM'][k])<1e-9 for k in metrics);trajectories.append(dict(epoch=epoch,**summary));t['epoch']=epoch;sem_tables.append(t)
    pd.DataFrame(trajectories).to_csv(out/'SEM_trajectory.csv',index=False)
    r129=REPO/'Experiments/R129_OpticalPriorHybrid';old=pd.read_csv(r129/'results/long_training_review_20260913_v2/sem_measurements.csv');old=old[old.step==8192]
    new=sem_tables[-1];a=new.groupby('pillar')[metrics].median();b=old.groupby('pillar')[metrics].median();paired=[]
    for k in metrics:
        change=a[k]-b[k];gain=change if k=='correlation' else -change;paired.append(dict(metric=k,V42_improved=int((gain>1e-7).sum()),V42_worsened=int((gain< -1e-7).sum()),median_V42_minus_R129=float(change.median())))
    pd.DataFrame(paired).to_csv(out/'SEM_paired_vs_R129.csv',index=False)
    def signature(points):
        origin=points.mean(0);z=points-origin
        def residual(c):
            radii=np.linalg.norm(z-c,axis=1);return radii-radii.mean()
        fit=least_squares(residual,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12);d=z-fit.x;r=np.linalg.norm(d,axis=1);a=np.mod(np.arctan2(d[:,1],d[:,0]),2*np.pi);order=np.argsort(a);a=a[order];v=r[order]
        return np.interp(np.arange(720)*2*np.pi/720,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[v[-1],v,v[0]]),r.mean()
    points=np.load(run/'evaluations/epoch32/real/sem_points.npz');truth={i:signature(points[f'SEM_{i}']) for i in range(1,37)}
    scale=5000/float(loadmat(ROOT/'validation/sem_reference.mat',variable_names=['opt_pitch'])['opt_pitch'].item());sem_error={k:0. for k in ['radial_nm','correlation','diameter_error_nm','centered_shape_nm']}
    for row in new.itertuples():
        a,ra=signature(points[f'{row.exposure}_{row.pillar}']);b,rb=truth[row.pillar]
        values=[np.mean(abs(a-b))*scale,np.corrcoef(a,b)[0,1],2*abs(ra-rb)*scale,np.mean(abs((a-a.mean())-(b-b.mean())))*scale]
        for key,value in zip(sem_error,values):sem_error[key]=max(sem_error[key],abs(value-getattr(row,key)))
    assert max(sem_error.values())<.001
    plan=load(ROOT/'config/final_evaluation_plan.json');scope=reader(plan);measurements=ROOT/'results/continuous';centers=pd.read_csv(measurements/'centers.csv');assert len(centers)==1809;max_difference=0.
    for rec in continuous['records']:
        for key in ['image','centers','boundaries']:assert sha(rec[key]['path'])==rec[key]['sha256']
        pts=np.load(rec['boundaries']['path']);table=pd.read_csv(rec['centers']['path'])
        for i,row in enumerate(table.itertuples()):
            xy=pts['inflection_points'][i];origin=xy.mean(0);z=xy-origin
            def residual(c):
                radii=np.linalg.norm(z-c,axis=1);return radii-radii.mean()
            fit=least_squares(residual,np.zeros(2),xtol=1e-12,ftol=1e-12,gtol=1e-12);c=fit.x+origin;r=np.linalg.norm(z-fit.x,axis=1).mean()
            diff=max(abs(c[0]-row.lsc_center_x_px),abs(c[1]-row.lsc_center_y_px),abs(r-row.lsc_radius_px));assert diff<1e-4;max_difference=max(diff,max_difference)
    allsumm=[];data_cfg=load(plan['configuration']['path']);comparisons=[]
    for population in ['locked120','within_session194']:
        pairs=pd.read_csv(measurements/(population+'_pairs.csv'));check,pillars=scope['pair_table'](centers,pairs,data_cfg,'V42_clean32')
        for k in ['measured_step_um','nominal_abs_error_nm','within_grid_sd_nm','cross_axis_abs_nm']:assert float(abs(check[k]-pairs[k]).max())<1e-8
        s=scope['summarize_pairs'](pairs);s['population']=population;allsumm.append(s)
        old=pd.read_csv(r129/'results/continuous_lsc/measurements/R129'/(population+'_pairs.csv'));j=pairs.merge(old,on=['sequence','start_frame_index','end_frame_index'],suffixes=('_V42','_R129'),validate='one_to_one')
        for k in ['nominal_abs_error_nm','within_grid_sd_nm','cross_axis_abs_nm']:
            d=j[k+'_V42']-j[k+'_R129'];comparisons.append(dict(population=population,metric=k,V42_improved=int((d< -1e-7).sum()),V42_worsened=int((d>1e-7).sum()),median_change=float(d.median())))
    summary=pd.concat(allsumm);summary.to_csv(out/'V42_LSC_summary.csv',index=False);pd.DataFrame(comparisons).to_csv(out/'LSC_paired_vs_R129.csv',index=False)
    dev=[dict(epoch=e,loss=load(run/f'evaluations/epoch{e:02d}/dev.json')['mean_loss']) for e in range(33)];pd.DataFrame(dev).to_csv(out/'dev_trajectory.csv',index=False)
    # Preserve R129 unchanged and the original V42 source/weight identities.
    for rec in load(ROOT/'config/provenance.json')['protected']:assert sha(rec['path'])==rec['sha256']
    for rec in plan['protected_sources']:assert sha(rec['path'])==rec['sha256']
    save(out/'verified.json',dict(completed_utc=now(),source=record(__file__),epochs=32,unique_updates=4096,actual_update_calls=len(rows),replayed_updates=replays,unique_parent_pairs=16384,independently_rebuilt_updates=rebuild,independently_rebuilt_parent_pairs=len(rebuild)*4,fresh_initialization_reproduced=True,final_optimizer_step4096=True,SEM_rows=108*5,independent_final_SEM_refits=108,SEM_max_refit_differences=sem_error,full_reconstructed_frames=201,independent_LSC_refits=1809,max_LSC_refit_difference_px=max_difference,all_declared_R129_sources_unchanged=True,shared_calibration_not_new_independent_evidence=True,model_promoted=False,final_checkpoint=completion['checkpoint'],SEM_trajectory=trajectories))
    print(pd.DataFrame(trajectories).to_string(index=False));print(summary[summary.scope=='all_four_sequences'].to_string(index=False))
if __name__=='__main__':main()
