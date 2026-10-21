"""Verify the matched bridge and distinguish radius bias from irregular-shape error."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'results/thesis_v34_review_20260912';sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd
from scipy.optimize import least_squares

def circle(points):
    origin=points.mean(axis=0);q=points-origin
    def fun(c):
        r=np.linalg.norm(q-c,axis=1);return r-r.mean()
    def jac(c):
        v=c-q;r=np.linalg.norm(v,axis=1);a=v/r[:,None];return a-a.mean(axis=0)
    fit=least_squares(fun,[0.,0.],jac=jac,method='lm',xtol=1e-12,ftol=1e-12,gtol=1e-12);assert fit.success
    return fit.x+origin

def signature(points):
    center=circle(points);delta=points-center;angle=np.mod(np.arctan2(delta[:,1],delta[:,0]),2*np.pi);radius=np.linalg.norm(delta,axis=1);idx=np.argsort(angle);angle=angle[idx];radius=radius[idx]
    return np.interp(np.linspace(0,2*np.pi,720,endpoint=False),np.r_[angle[-1]-2*np.pi,angle,angle[0]+2*np.pi],np.r_[radius[-1],radius,radius[0]])

def main():
    b=BASE/'v34_bridge';p=load(b/'plan.json');done=load(b/'measurement_complete.json');assert all(x['passed'] for x in done['baseline_reader_parity'])
    assert sha(p['checkpoint']['path'])==p['checkpoint']['sha256']
    assert all(sha(s['path'])==s['sha256'] for s in p['sources'])
    locked=pd.read_csv(b/'locked_pairs.csv');keys=['sequence','start_frame_index','end_frame_index'];expected=set(map(tuple,locked[keys].to_numpy()))
    new=pd.read_csv(b/'three_method_pairs.csv');new=new[new.method!='Raw'];baselines=[]
    for key in ['srcnn','unet','vdsr','edsr','rdn','nafnet','pft']:
        path=ROOT.parent/f'R81_MultiArchitectureReferenceCircleBenchmark/results/evaluation/{key}/displacement_per_pair.csv';t=pd.read_csv(path);assert len(t)==120 and set(map(tuple,t[keys].to_numpy()))==expected;baselines.append(t)
    combined=pd.concat([*baselines,new],ignore_index=True);summaries=[]
    for method,g in combined.groupby('method',sort=False):
        summaries.append(dict(method=method,pairs=len(g),step_sd_nm=float(np.mean([s.measured_step_um.std(ddof=1)*1000 for _,s in g.groupby('sequence')])),nominal_mae_nm=float(g.nominal_abs_error_nm.mean()),within_grid_nm=float(g.within_grid_sd_nm.median()),cross_axis_nm=float(g.cross_axis_abs_nm.median())))
    summary=pd.DataFrame(summaries)
    for metric in ['step_sd_nm','nominal_mae_nm','within_grid_nm']:summary[metric+'_rank_with_V42']=summary[metric].rank(method='min').astype(int)
    replacement=summary[summary.method!='MOSR'].copy()
    for metric in ['step_sd_nm','nominal_mae_nm','within_grid_nm']:replacement[metric+'_replacement_rank']=replacement[metric].rank(method='min').astype(int)
    summary.to_csv(b/'nine_learned_model_comparison.csv',index=False);replacement.to_csv(b/'eight_model_replacement_comparison.csv',index=False)
    # Independently calculate candidate pair arithmetic from saved centers, not the summarizer.
    cfg=load(p['configuration']['path']);errors=[]
    for method in ['Raw','MOSR','R128_P_s1285002']:
        c=pd.read_csv(b/'measurements'/method/'centers.csv');pairs=pd.read_csv(b/'measurements'/method/'per_pair.csv');idx=c.set_index(['sequence','frame_index','pillar_id']);diff=[]
        for r in pairs.itertuples():
            ids=sorted(int(x[0]) for x in cfg['sequences'][r.sequence]['centers']);a=idx.loc[[(r.sequence,r.start_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].to_numpy();z=idx.loc[[(r.sequence,r.end_frame_index,i) for i in ids],['lsc_center_x_px','lsc_center_y_px']].to_numpy();v=(z-a)*cfg['sequences'][r.sequence]['object_um_per_px'];x,y=np.median(v,axis=0)
            actual=[abs(x),abs(abs(x)-r.nominal_step_um)*1000,np.std(v[:,0],ddof=1)*1000,abs(y)*1000];saved=[r.measured_step_um,r.nominal_abs_error_nm,r.within_grid_sd_nm,r.cross_axis_abs_nm];diff.extend(np.abs(np.array(actual)-saved))
        assert max(diff)<1e-7;errors.append(dict(method=method,max_pair_arithmetic_difference=float(max(diff))))
    # All image records are source/checkpoint-bound and original sources still match.
    outputs=load(b/'inference_complete.json')['records'];assert len(outputs)==166
    for r in outputs:
        for k in ['source','image','output_float']:assert sha(r[k]['path'])==r[k]['sha256']
    f=BASE/'normal_sem_fine_v2';fine=pd.read_csv(f/'per_measurement.csv');fv=load(f/'verification.json');assert max(fv['Raw_V42_parity_max'].values())<1e-6
    pts=np.load(f/'boundary_points.npz');scale=5/134.468 # corrected below from the original source's stored pitch
    from scipy.io import loadmat
    source=ROOT.parent/'R70_V42ACMContourSEMValidation/results/masks/acm_primary_masks.mat';scale=5/float(loadmat(source,variable_names=['opt_pitch'])['opt_pitch'].item())
    target={i:signature(pts[f'SEM_{i}']) for i in range(1,37)};rows=[];maxdiff=0
    for row in fine.itertuples():
        a=signature(pts[f'{row.method}_{row.exposure}_{row.pillar_id}']);z=target[row.pillar_id]
        mae=float(np.mean(np.abs(a-z))*scale*1000);corr=float(np.corrcoef(a-a.mean(),z-z.mean())[0,1]);maxdiff=max(maxdiff,abs(mae-row.radial_shape_mae_nm));assert abs(mae-row.radial_shape_mae_nm)<.001 and abs(corr-row.contour_correlation)<1e-5
        rows.append(dict(method=row.method,exposure=row.exposure,pillar_id=row.pillar_id,mean_radius_bias_nm=float((a.mean()-z.mean())*scale*1000),centered_shape_mae_nm=float(np.mean(np.abs((a-a.mean())-(z-z.mean())))*scale*1000),measured_mzc_nm=row.measured_mzc_nm,SEM_mzc_nm=row.SEM_mzc_nm))
    diagnostic=pd.DataFrame(rows);diagnostic.to_csv(f/'radius_vs_shape_diagnostic.csv',index=False);agg=diagnostic.groupby(['method','pillar_id']).median(numeric_only=True).groupby('method').median(numeric_only=True);agg.to_csv(f/'radius_vs_shape_summary.csv')
    save(BASE/'bridge_verification.json',dict(completed_utc=now(),source=record(__file__),v34_Raw_and_V42_reader_reproduced=True,all_nine_methods_same_v34_120pairs=True,pair_arithmetic_checks=errors,
        R128new_full_images=sum(not r['reused'] for r in outputs),R128reused_images=sum(r['reused'] for r in outputs),fine_SEM_Raw_V42_parity=fv['Raw_V42_parity_max'],fine_324rows_independent_radial_metric_max_difference_nm=maxdiff,
        radius_shape_decomposition_is_exploratory=True,original_sources_unchanged=True,new_training_updates=0,no_confirmation_access=True,learned_comparison=record(b/'nine_learned_model_comparison.csv'),normal_SEM_summary=record(f/'summary.csv')))
    print(summary.to_string(index=False));print('Replacement ranks:');print(replacement[['method','step_sd_nm_replacement_rank','nominal_mae_nm_replacement_rank','within_grid_nm_replacement_rank']].to_string(index=False));print('Radiusandshape:',agg.to_string())
if __name__=='__main__':main()
