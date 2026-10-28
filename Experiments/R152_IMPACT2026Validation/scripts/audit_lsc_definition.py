"""Independent displacement-definition and geometric-LSC audit, without replacing results."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/definition_audit';OUT.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'sources'))
from reference_circle_core import fit_lsc
SEQS=['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um']
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def main():
    new=pd.read_csv(ROOT/'results/full120/centers.csv');old=pd.read_csv(ROOT/'sources/historical_centers.csv');old=old[old.method=='MOSR'].copy();old['method']='V42'
    centers=pd.concat([new,old],ignore_index=True);idx=centers.set_index(['sequence','method','frame_index','pillar_id']).sort_index();locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv')
    conf=json.loads((ROOT/'sources/sequence_config.json').read_text(encoding='utf-8-sig'));rows=[];pillars=[]
    for pair in locked.itertuples():
        spec=conf['sequences'][pair.sequence];s=spec['object_um_per_px'];nom=spec['nominal_step_um']*1000
        for method in ['Raw','Wiener','V42','R152']:
            a=idx.loc[(pair.sequence,method,pair.start_frame_index)].sort_index();b=idx.loc[(pair.sequence,method,pair.end_frame_index)].sort_index();assert a.index.equals(b.index) and len(a)==9
            dx=(b.lsc_center_x_px.to_numpy()-a.lsc_center_x_px.to_numpy())*s*1000;dy=(b.lsc_center_y_px.to_numpy()-a.lsc_center_y_px.to_numpy())*s*1000
            mx=np.median(dx);my=np.median(dy)
            variants={'published_abs_median_dx':abs(mx),'vector_length_of_component_medians':np.hypot(mx,my),'median_of_nine_vector_lengths':np.median(np.hypot(dx,dy)),'abs_mean_dx':abs(dx.mean()),'vector_length_of_mean':np.hypot(dx.mean(),dy.mean())}
            for name,value in variants.items():rows.append(dict(sequence=pair.sequence,method=method,start=pair.start_frame_index,end=pair.end_frame_index,definition=name,step_nm=value,error_nm=value-nom,abs_error_nm=abs(value-nom),dy_median_nm=my,within_x_sd_nm=np.std(dx,ddof=1)))
            for pid,x,y in zip(a.index,dx,dy):pillars.append(dict(sequence=pair.sequence,method=method,start=pair.start_frame_index,end=pair.end_frame_index,pillar_id=int(pid),dx_nm=x,dy_nm=y,nominal_nm=nom,error_nm=-x-nom))
    detail=pd.DataFrame(rows);pd.DataFrame(pillars).to_csv(OUT/'per_pillar_displacement.csv',index=False);detail.to_csv(OUT/'definition_per_pair.csv',index=False)
    summaries=[]
    for (definition,method),g in detail.groupby(['definition','method'],sort=False):
        summaries.append(dict(definition=definition,method=method,mean_condition_step_sd_nm=np.mean([x.step_nm.std(ddof=1) for _,x in g.groupby('sequence')]),nominal_mae_nm=g.abs_error_nm.mean(),median_within_x_sd_nm=g.within_x_sd_nm.median(),median_abs_dy_nm=g.dy_median_nm.abs().median(),max_abs_dy_nm=g.dy_median_nm.abs().max()))
    pd.DataFrame(summaries).to_csv(OUT/'definition_summary.csv',index=False)
    published=pd.read_csv(ROOT/'results/full120/per_pair.csv');cmp=detail[(detail.definition=='published_abs_median_dx')&detail.method.ne('V42')].merge(published,left_on=['sequence','method','start','end'],right_on=['sequence','method','start_frame_index','end_frame_index'])
    maxdiff=float(abs(cmp.step_nm-cmp.measured_step_um*1000).max());assert maxdiff<1e-7
    decomp=[];pp=pd.DataFrame(pillars)
    for (seq,m),g in pp.groupby(['sequence','method']):
        mat=g.pivot(index=['start','end'],columns='pillar_id',values='error_nm').to_numpy();common=mat.mean(axis=1);residual=mat-common[:,None];corr=np.corrcoef(mat,rowvar=False)
        decomp.append(dict(sequence=seq,method=m,common_mean_error_sd_nm=np.std(common,ddof=1),common_median_error_sd_nm=np.std(np.median(mat,axis=1),ddof=1),median_pair_within_sd_nm=np.median(np.std(mat,axis=1,ddof=1)),mean_inter_pillar_correlation=np.mean(corr[np.triu_indices(9,1)]),common_mean_square_fraction=np.mean(common**2)/np.mean(mat**2),common_mean_error_nm=common.mean(),note='Descriptive common motion/error; cannot identify platform versus shared optical bias without frame-level reference.'))
    pd.DataFrame(decomp).to_csv(OUT/'common_and_differential_motion.csv',index=False)
    checks=[]
    for n in [64,96,720]:
        angles=np.arange(n)*2*np.pi/n;center=np.array([17.234,22.789]);r=7.6;points=center+r*np.c_[np.cos(angles),np.sin(angles)]
        for shift in [np.array([0.,0.]),np.array([.25,-.4]),np.array([-7.24637681,.03])]:
            circle=fit_lsc(points+shift);error=float(np.linalg.norm([circle.cx-center[0]-shift[0],circle.cy-center[1]-shift[1]]));assert error<1e-8
            checks.append(dict(points=n,shift=shift.tolist(),center_error_px=error,radius_error_px=abs(circle.radius-r)))
    save(OUT/'calculation_verification.json',dict(passed=True,geometric_lsc_objective='sum of squared radial-distance residuals, no command term',published_pair_recomputation_max_difference_nm=maxdiff,exact_circle_checks=checks,units='native pixels to um once, then nm',primary_displacement='absolute median of 9 signed x-center differences; y is retained separately',reference='nominal commanded step, not PI feedback'))
    print(pd.DataFrame(summaries).to_string(index=False));print(pd.DataFrame(decomp).to_string(index=False))
if __name__=='__main__':main()
