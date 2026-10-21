import os
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[key]='1'
from common import *
import argparse
import numpy as np,pandas as pd
from scipy import stats

METRICS=['bias_nm','mae_nm','rmse_nm','error_sd_nm','max_abs_nm','transverse_rms_nm']
def metrics(g):
    e=g.error_nm.to_numpy();cross=g.transverse_nm.to_numpy()
    return dict(n=len(e),bias_nm=float(e.mean()),mae_nm=float(np.abs(e).mean()),rmse_nm=float(np.sqrt(np.mean(e**2))),error_sd_nm=float(e.std(ddof=1)),max_abs_nm=float(np.abs(e).max()),transverse_rms_nm=float(np.sqrt(np.mean(cross**2))))

def bootstrap(values,block=1,n=10000,seed=136):
    x=np.asarray(values,float);rng=np.random.default_rng(seed);count=len(x)
    if block==1:ids=rng.integers(0,count,(n,count))
    else:
        starts=rng.integers(0,count,(n,int(np.ceil(count/block))));ids=((starts[:,:,None]+np.arange(block))%count).reshape(n,-1)[:,:count]
    means=x[ids].mean(1);return np.quantile(means,[.025,.975]).tolist()

def write_csv(df,p):df.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.10g')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--partial',action='store_true');ap.add_argument('--models',nargs='+',default=['Raw','R61','R129']);ap.add_argument('--out');ap.add_argument('--input',default='results/readouts');ap.add_argument('--primary-roi',default='primary');ap.add_argument('--primary-reader',default='highpass');args=ap.parse_args()
    files=[f for f in sorted((ROOT/args.input).glob('*/*.csv')) if f.parent.name in args.models];assert files
    d=pd.concat([pd.read_csv(f) for f in files],ignore_index=True);plan=load(ROOT/'config/plan.json')
    out=ROOT/(args.out or ('results/progress_tables' if args.partial else 'results/tables'));out.mkdir(parents=True,exist_ok=True)
    coverage=d.groupby(['model','kind','roi','reader','precision','status'],dropna=False).size().reset_index(name='count');write_csv(coverage,out/'coverage.csv')
    main=d[(d.roi==args.primary_roi)&(d.reader==args.primary_reader)&(d.precision=='full')&(d.status=='ok')].copy()
    if not args.partial:
        assert all(len(main[main.model==m])==1800 for m in args.models)
        for m in args.models:
            if m!='Raw':assert load(ROOT/'results'/m/'complete.json')['frames']==930
    fit=main[(main.model=='Raw')&(main.run_index<=6)&(main.kind=='start')]
    assert len(fit)==180,'Need all six raw calibration scans'
    p=fit.pi_dy_um.to_numpy();v=fit[['dx_px','dy_px']].to_numpy();q=np.sum(p[:,None]*v,axis=0)/np.sum(p*p)
    u=q/np.linalg.norm(q);perp=np.array([-u[1],u[0]]);scale=1/np.linalg.norm(q)
    calrows=[]
    for run,g in fit.groupby('run_index'):
        yy=g.pi_dy_um.to_numpy();vv=g[['dx_px','dy_px']].to_numpy();qq=np.sum(yy[:,None]*vv,axis=0)/np.sum(yy**2)
        calrows.append(dict(run_index=int(run),um_per_px=float(1/np.linalg.norm(qq)),image_x_px_per_um=float(qq[0]),image_y_px_per_um=float(qq[1])))
    calibration=dict(raw_calibration_runs=6,evaluation_runs=24,image_vector_px_per_um=q.tolist(),axis_unit_vector=u.tolist(),transverse_unit_vector=perp.tolist(),nominal_um_per_px=.1725,estimated_um_per_px=float(scale),nominal_relative_scale_difference_percent=float((scale/.1725-1)*100),per_run=calrows,scope='PI-referenced operational calibration,not SI-traceable independent scale calibration',transverse='image perpendicular motion only;PI X direction and scale not independently excited')
    save(out/'calibration.json',calibration)
    views=[]
    for view,sc,minimum in [('nominal_all30',.1725,1),('nominal_late24',.1725,7),('calibrated_late24',scale,7)]:
        part=d[(d.status=='ok')&(d.run_index>=minimum)].copy();part['view']=view
        xy=part[['dx_px','dy_px']].to_numpy();part['image_along_um']=xy@u*sc;part['error_nm']=(part.image_along_um-part.pi_dy_um)*1000;part['transverse_nm']=xy@perp*sc*1000
        views.append(part)
    enriched=pd.concat(views,ignore_index=True);write_csv(enriched,out/'all_measurements.csv')
    primary=enriched[(enriched.roi==args.primary_roi)&(enriched.reader==args.primary_reader)&(enriched.precision=='full')]
    runs=[]
    for keys,g in primary.groupby(['view','model','run','run_index','time_block','kind']):runs.append(dict(zip(['view','model','run','run_index','time_block','kind'],keys),**metrics(g)))
    runs=pd.DataFrame(runs);write_csv(runs,out/'per_scan.csv')
    summaries=[]
    for keys,g in runs.groupby(['view','model','kind']):
        row=dict(zip(['view','model','kind'],keys),scans=len(g))
        for name in METRICS:
            x=g[name].to_numpy();lo,hi=bootstrap(x)
            row.update({name+'_mean':float(x.mean()),name+'_sd_between_scans':float(x.std(ddof=1)),name+'_ci95_low':lo,name+'_ci95_high':hi})
        row['largest_error_nm']=float(g.max_abs_nm.max());summaries.append(row)
    summary=pd.DataFrame(summaries);write_csv(summary,out/'summary.csv')
    positions=[]
    for keys,g in primary.groupby(['view','model','kind','j']):
        e=g.error_nm.to_numpy();positions.append(dict(zip(['view','model','kind','position_index'],keys),n=len(e),pi_displacement_um=float(g.pi_dy_um.mean()),bias_nm=float(e.mean()),repeatability_sd_nm=float(e.std(ddof=1)),observed_min_nm=float(e.min()),observed_max_nm=float(e.max()),mae_nm=float(np.abs(e).mean()),transverse_sd_nm=float(g.transverse_nm.std(ddof=1))))
    write_csv(pd.DataFrame(positions),out/'per_position.csv')
    # Repeatability is across scans at each matched position, not across positions in one scan.
    repeatability=[];repeatability_deltas=[]
    for (view,kind),g in primary.groupby(['view','kind']):
        matrices={}
        for model,mg in g.groupby('model'):
            matrix=mg.pivot(index='run_index',columns='j',values='error_nm').sort_index()
            if matrix.shape[0]<3 or matrix.isna().any().any():continue
            matrices[model]=matrix
            values=matrix.to_numpy();rng=np.random.default_rng(136);ids=rng.integers(0,len(values),(10000,len(values)))
            boot=np.std(values[ids],axis=1,ddof=1).mean(axis=1);lo,hi=np.quantile(boot,[.025,.975]);sds=values.std(axis=0,ddof=1)
            repeatability.append(dict(view=view,kind=kind,model=model,scans=len(values),positions=values.shape[1],mean_position_sd_nm=float(sds.mean()),maximum_position_sd_nm=float(sds.max()),ci95_low=float(lo),ci95_high=float(hi)))
        for candidate,reference in [('R61','Raw'),('R129','Raw'),('R129','R61')]:
            if candidate not in matrices or reference not in matrices:continue
            common=matrices[candidate].index.intersection(matrices[reference].index)
            if len(common)<3:continue
            a=matrices[candidate].loc[common].to_numpy();b=matrices[reference].loc[common].to_numpy();rng=np.random.default_rng(136);ids=rng.integers(0,len(common),(10000,len(common)))
            delta=np.std(a[ids],axis=1,ddof=1).mean(1)-np.std(b[ids],axis=1,ddof=1).mean(1);lo,hi=np.quantile(delta,[.025,.975])
            repeatability_deltas.append(dict(view=view,kind=kind,candidate=candidate,reference=reference,paired_scans=len(common),difference_nm=float(a.std(0,ddof=1).mean()-b.std(0,ddof=1).mean()),ci95_low=float(lo),ci95_high=float(hi)))
    write_csv(pd.DataFrame(repeatability),out/'repeatability.csv');write_csv(pd.DataFrame(repeatability_deltas),out/'repeatability_comparisons.csv')
    paired=[]
    for (view,kind),g in runs.groupby(['view','kind']):
        for candidate,reference in [('R61','Raw'),('R129','Raw'),('R129','R61')]:
            left=g[g.model==candidate].set_index('run_index');right=g[g.model==reference].set_index('run_index');ids=sorted(set(left.index)&set(right.index))
            if not ids:continue
            for name in METRICS:
                delta=left.loc[ids,name].to_numpy()-right.loc[ids,name].to_numpy();lo,hi=bootstrap(delta);blo,bhi=bootstrap(delta,block=3)
                paired.append(dict(view=view,kind=kind,candidate=candidate,reference=reference,metric=name,paired_scans=len(ids),candidate_minus_reference_mean_nm=float(delta.mean()),ci95_low=lo,ci95_high=hi,block3_ci95_low=blo,block3_ci95_high=bhi,improved_scans=int((delta<0).sum()) if name!='bias_nm' else None,worsened_scans=int((delta>0).sum()) if name!='bias_nm' else None,tied_scans=int((delta==0).sum()),meaning='negative is smaller; signed bias must be judged relative to zero'))
    write_csv(pd.DataFrame(paired),out/'paired_comparisons.csv')
    sensitivity=[]
    for keys,g in enriched.groupby(['view','model','kind','roi','reader','precision']):sensitivity.append(dict(zip(['view','model','kind','roi','reader','precision'],keys),**metrics(g)))
    write_csv(pd.DataFrame(sensitivity),out/'sensitivity.csv')
    sensitivity_paired=[]
    for keys,g in enriched[(enriched.view=='nominal_all30')&(enriched.precision=='full')].groupby(['kind','roi','reader']):
        vals=g.assign(a=g.error_nm.abs()).groupby(['run_index','model']).a.mean().unstack('model')
        for candidate,reference in [('R61','Raw'),('R129','Raw'),('R129','R61')]:
            if candidate not in vals or reference not in vals:continue
            matched=vals[[candidate,reference]].dropna();delta=(matched[candidate]-matched[reference]).to_numpy();lo,hi=bootstrap(delta);blo,bhi=bootstrap(delta,3)
            sensitivity_paired.append(dict(kind=keys[0],roi=keys[1],reader=keys[2],candidate=candidate,reference=reference,paired_scans=len(matched),reference_mae_nm=float(matched[reference].mean()),candidate_mae_nm=float(matched[candidate].mean()),delta_nm=float(delta.mean()),ci95_low=lo,ci95_high=hi,block3_low=blo,block3_high=bhi,improved=int((delta<0).sum()),worsened=int((delta>0).sum())))
    write_csv(pd.DataFrame(sensitivity_paired),out/'reader_sensitivity_paired.csv')
    drift=[]
    for keys,g in runs.groupby(['view','model','kind']):
        for name in ['bias_nm','mae_nm','error_sd_nm']:
            if len(g)<3:continue
            s=stats.linregress(g.run_index,g[name]);drift.append(dict(zip(['view','model','kind'],keys),metric=name,slope_nm_per_scan=float(s.slope),r=float(s.rvalue),p_descriptive=float(s.pvalue)))
    write_csv(pd.DataFrame(drift),out/'time_drift.csv')
    blocks=runs.groupby(['view','model','kind','time_block'])[METRICS].mean().reset_index();write_csv(blocks,out/'time_blocks.csv')
    closure=[]
    for keys,g in primary.groupby(['view','model','run','run_index']):
        adj=g[g.kind=='adjacent'].sort_values('j');starts=g[g.kind=='start'].set_index('j');both=adj[adj.j.isin(starts.index)]
        if len(both)==30:
            err=both.image_along_um.cumsum().to_numpy()-starts.loc[both.j,'image_along_um'].to_numpy();closure.append(dict(zip(['view','model','run','run_index'],keys),closure_endpoint_nm=float(err[-1]*1000),closure_max_abs_nm=float(np.abs(err).max()*1000)))
    write_csv(pd.DataFrame(closure),out/'path_closure.csv')
    # Worst cases remain in the population and are explicitly easy to locate.
    worst=primary.assign(abs_error_nm=primary.error_nm.abs()).sort_values('abs_error_nm',ascending=False).groupby(['view','model','kind'],sort=False).head(5);write_csv(worst,out/'largest_errors.csv')
    components=[dict(component='repeated capture residual spread',available=True,evidence='per_position.csv and per_scan.csv',qualification='observed PI-referenced residuals include reference noise;not automatically all optical uncertainty'),dict(component='scale calibration',available=True,evidence='calibration.json',qualification='nominal scale and early6 PI operational fit;no independent certificate'),dict(component='PI reference calibration uncertainty',available=False,evidence='not supplied',qualification='no total expanded uncertainty reported'),dict(component='camera and PI timing uncertainty',available=False,evidence='user confirms synchronous feedback;no timing calibration',qualification='recorded timestamps alone do not establish residual timing error'),dict(component='between days and specimens',available=False,evidence='one sample and session',qualification='repeatability scope only')]
    save(out/'uncertainty_scope.json',dict(components=components,total_expanded_uncertainty=None))
    save(out/'analysis_complete.json',dict(partial=args.partial,created_utc=now(),input_files=len(files),input_rows=len(d),main_valid_rows=len(main),failed_rows=int((d.status!='ok').sum()),calibration=calibration,paired_bootstrap_replicates=10000,bootstrap_unit='complete scan',source_plan=record(ROOT/'config/plan.json')))
    print(summary[['view','model','kind','scans','mae_nm_mean','error_sd_nm_mean','largest_error_nm']].to_string(index=False),flush=True)
if __name__=='__main__':main()
