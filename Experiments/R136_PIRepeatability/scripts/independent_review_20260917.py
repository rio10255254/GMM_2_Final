"""Read-only recheck of supplied three-method ZIP, centers, PI joins and statistics."""
from pathlib import Path
import json,hashlib,zipfile,io,time
import numpy as np,pandas as pd
from scipy.optimize import least_squares
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    text=json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)
    with Path(p).open('x',encoding='utf-8') as f:f.write(text)
def main():
    out=ROOT/'results/independent_review_20260917';out.mkdir(exist_ok=False);archive=ROOT/'output/R136_LSC_Three_Method_Results.zip';plan=load(ROOT/'config/plan.json');cfg=load(ROOT/'config/lsc_plan.json');checks=[]
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for info in z.infolist():
            if info.is_dir():continue
            local=ROOT/info.filename;content=z.read(info.filename);checks.append(dict(name=info.filename,local_exists=local.is_file(),exact=local.is_file() and hashlib.sha256(content).hexdigest()==sha(local)))
        prefix='results/lsc/analysis/tables/'
        centers=pd.read_csv(io.BytesIO(z.read(prefix+'all_circle_centers.csv')));reported=pd.read_csv(io.BytesIO(z.read(prefix+'all_measurements.csv')));published=pd.read_csv(io.BytesIO(z.read(prefix+'readable_lsc_summary.csv')));paired=pd.read_csv(io.BytesIO(z.read(prefix+'paired_comparisons.csv')))
    pd.DataFrame(checks).to_csv(out/'zip_local_comparison.csv',index=False);assert all(x['exact'] for x in checks if x['name'].startswith(('reports/R136_LSC_RESULTS.md','config/','results/lsc/analysis/tables/')))
    assert len(centers)==25110 and not centers.duplicated(['model','run','index','pillar_id']).any();assert centers.groupby('model').size().to_dict()=={'R129':8370,'R61':8370,'Raw':8370}
    pi={};timing=[]
    for run in plan['runs']:
        file=Path(run['positions']['path']);assert sha(file)==run['positions']['sha256'];t=pd.read_csv(file);assert len(t)==31
        for i,r in enumerate(t.itertuples()):pi[run['run'],i]=(float(r.x),float(r.y))
        stamps=pd.to_datetime(t.recorded_at);timing.append(dict(run_index=run['run_index'],run=run['run'],duration_seconds=float((stamps.iloc[-1]-stamps.iloc[0]).total_seconds()),median_interframe_seconds=float(stamps.diff().dt.total_seconds().median())))
    pd.DataFrame(timing).to_csv(out/'capture_timing.csv',index=False)
    for f in plan['frames']:
        assert np.allclose(pi[f['run'],f['index']],[f['pi_x_um'],f['pi_y_um']],rtol=0,atol=1e-12)
    assert len(plan['frames'])==930 and len({f['source']['sha256'] for f in plan['frames']})==930
    for name,model in plan['models'].items():assert sha(model['checkpoint']['path'])==model['checkpoint']['sha256']
    rows=[];maxfit=0.;fitcount=0
    for (model,run,ri),g in centers.groupby(['model','run','run_index']):
        c=g.sort_values(['index','pillar_id'])[['center_x_px','center_y_px','radius_px']].to_numpy().reshape(31,9,3)
        with np.load(ROOT/f'results/lsc/centers/{model}/{run}.npz',allow_pickle=False) as p:points=p['points']
        assert points.shape==(31,9,64,2)
        for index in range(31):
            for pillar in range(9):
                xy=points[index,pillar];origin=xy.mean(0);z=xy-origin;r0=np.linalg.norm(z,axis=1).mean()
                def fun(v):return np.linalg.norm(z-v[:2],axis=1)-v[2]
                def jac(v):
                    delta=v[:2]-z;radius=np.linalg.norm(delta,axis=1);return np.column_stack((delta/radius[:,None],-np.ones(len(z))))
                solved=least_squares(fun,[0.,0.,r0],jac=jac,method='lm',ftol=1e-12,xtol=1e-12,gtol=1e-12);error=float(np.linalg.norm(solved.x[:2]+origin-c[index,pillar,:2]));assert error<1e-4;maxfit=max(maxfit,error);fitcount+=1
        for kind,i,j in [('adjacent',i-1,i) for i in range(1,31)]+[('start',0,j) for j in range(1,31)]:
            d=np.median(c[j,:,:2]-c[i,:,:2],axis=0);dp=np.array(pi[run,j])-pi[run,i];rows.append(dict(model=model,run=run,run_index=int(ri),kind=kind,i=i,j=j,dx_px=float(d[0]),dy_px=float(d[1]),pi_dy_um=float(dp[1])))
    derived=pd.DataFrame(rows);assert len(derived)==5400;keys=['model','run','kind','i','j'];original=reported[reported.view=='nominal_all30'];joined=derived.merge(original,on=keys,validate='one_to_one',suffixes=('_new','_old'));assert len(joined)==5400
    maxdelta=float(np.max(np.abs(joined[['dx_px_new','dy_px_new']].values-joined[['dx_px_old','dy_px_old']].values)));assert maxdelta<1e-6
    fit=derived[(derived.model=='Raw')&(derived.run_index<=6)&(derived.kind=='start')];displacement=fit.pi_dy_um.to_numpy();q=np.sum(displacement[:,None]*fit[['dx_px','dy_px']].values,axis=0)/np.sum(displacement**2);u=q/np.linalg.norm(q);scale=1/np.linalg.norm(q);cal=load(ROOT/'results/lsc/analysis/tables/calibration.json');assert np.allclose(q,cal['image_vector_px_per_um'],rtol=0,atol=1e-10)
    statistics=[];deltas=[];maxstats=0.
    for view,multiplier,first in [('nominal_all30',.1725,1),('nominal_late24',.1725,7),('calibrated_late24',scale,7)]:
        part=derived[derived.run_index>=first].copy();part['error']=(part[['dx_px','dy_px']].values@u*multiplier-part.pi_dy_um.values)*1000
        for (model,kind),g in part.groupby(['model','kind']):
            matrix=g.pivot(index='run_index',columns='j',values='error').sort_index();values=matrix.to_numpy();assert values.shape==(31-first,30);stat=dict(view=view,model=model,kind=kind,scans=len(matrix),mae_nm=float(np.abs(values).mean()),repeatability_nm=float(values.std(axis=0,ddof=1).mean()),maximum_error_nm=float(np.abs(values).max()));statistics.append(stat)
            match=published[(published.view==view)&(published.model==model)&(published.kind==kind)]
            if len(match):
                for name in ['mae_nm','repeatability_nm','maximum_error_nm']:maxstats=max(maxstats,abs(stat[name]-float(match.iloc[0][name])))
        for kind,g in part.groupby('kind'):
            scan=g.assign(abs_error=g.error.abs()).groupby(['run_index','model']).abs_error.mean().unstack('model');difference=(scan.R129-scan.R61).values;count=len(difference);rng=np.random.default_rng(136);ids=rng.integers(0,count,(10000,count));ci=np.quantile(difference[ids].mean(1),[.025,.975]);rng=np.random.default_rng(136);starts=rng.integers(0,count,(10000,int(np.ceil(count/3))));blocks=((starts[:,:,None]+np.arange(3))%count).reshape(10000,-1)[:,:count];bci=np.quantile(difference[blocks].mean(1),[.025,.975]);check=paired[(paired.view==view)&(paired.kind==kind)&(paired.candidate=='R129')&(paired.reference=='R61')&(paired.metric=='mae_nm')].iloc[0]
            assert np.allclose([difference.mean(),*ci,*bci],[check.candidate_minus_reference_mean_nm,check.ci95_low,check.ci95_high,check.block3_ci95_low,check.block3_ci95_high],rtol=0,atol=1e-4)
            deltas.append(dict(view=view,kind=kind,R129_minus_R61_nm=float(difference.mean()),ci95=ci.tolist(),block3_ci95=bci.tolist(),R129_better_scans=int((difference<0).sum()),scans=count))
    assert maxstats<1e-4;pd.DataFrame(statistics).to_csv(out/'independent_statistics.csv',index=False);save(out/'independent_paired_differences.json',deltas)
    # R129 uses80/16 here; all measured patches are far outside either80/16or16/16retention bands.
    x=centers.center_x_px.values;y=centers.center_y_px.values;clearance=float(np.min(np.concatenate([x-14,y-14,2063-x-14,1543-y-14])));assert clearance>96
    save(out/'verification.json',dict(archive_sha256=sha(archive),archive_entries=len(checks),zip_crc_passed=True,zip_local_matches=sum(x['exact'] for x in checks),zip_only_or_different=[x for x in checks if not x['exact']],raw_unique_declared_hashes=930,PI_csv_files_verified=30,PI_joined_frames=930,independent_circle_refits=fitcount,max_circle_difference_px=maxfit,independent_aggregate_pairs=5400,max_aggregate_coordinate_difference_px=maxdelta,independent_scale_um_per_px=float(scale),max_summary_difference_nm=maxstats,paired_intervals_and_block3_reproduced=True,minimum_measured_patch_clearance_px=clearance,source_files_unchanged=True,scope='Independent second calculation from suppliedZIP and local stored boundaries; no full neural rerun, no independent PI certificate or physical specimen identity audit'))
    print(pd.DataFrame(statistics).to_string(index=False));print('Verified:',fitcount,'circle fits,5400pair calculations,30PI CSVs; ZIP exact local copies',sum(x['exact'] for x in checks),'/',len(checks),'maxstaterror nm',maxstats)
if __name__=='__main__':main()
