"""Independent arithmetic, saved-boundary fits and full-output checks for LSC."""
import sys,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
import numpy as np,pandas as pd,cv2
from scipy.optimize import least_squares
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def alternate_fit(points):
    origin=points.mean(axis=0);u=points-origin
    def residual(c):
        r=np.linalg.norm(u-c,axis=1);return r-r.mean()
    def jacobian(c):
        v=c-u;r=np.linalg.norm(v,axis=1);j=v/r[:,None];return j-j.mean(axis=0)
    fit=least_squares(residual,np.zeros(2),jac=jacobian,method='lm',ftol=1e-12,xtol=1e-12,gtol=1e-12)
    assert fit.success
    return np.r_[fit.x+origin,np.linalg.norm(u-fit.x,axis=1).mean()]


def independent_pairs(centers,locked,config,method):
    rows=[]
    for pair in locked.itertuples(index=False):
        seq=pair.sequence;s=config['sequences'][seq];scale=s['object_um_per_px'];nominal=s['nominal_step_um']
        g=centers[centers.sequence==seq]
        a=g[g.frame_index==pair.start_frame_index].sort_values('pillar_id');b=g[g.frame_index==pair.end_frame_index].sort_values('pillar_id')
        assert len(a)==len(b)==9 and np.array_equal(a.pillar_id,b.pillar_id)
        d=(b[['lsc_center_x_px','lsc_center_y_px']].to_numpy()-a[['lsc_center_x_px','lsc_center_y_px']].to_numpy())*scale
        mx,my=np.median(d,axis=0);step=abs(mx)
        rows.append(dict(sequence=seq,start_frame_index=pair.start_frame_index,end_frame_index=pair.end_frame_index,method=method,
            aggregate_dx_um=float(mx),aggregate_dy_um=float(my),measured_step_um=float(step),
            nominal_abs_error_nm=float(abs(step-nominal)*1000),within_grid_sd_nm=float(np.sqrt(np.sum((d[:,0]-d[:,0].mean())**2)/8)*1000),cross_axis_abs_nm=float(abs(my)*1000)))
    return pd.DataFrame(rows)


def summarize(t):
    rows=[]
    def one(method,seq,g,scope):
        step=float(g.measured_step_um.std(ddof=1)*1000) if scope=='per_sequence' else float(np.mean([v.measured_step_um.std(ddof=1)*1000 for _,v in g.groupby('sequence')]))
        return dict(scope=scope,sequence=seq,method=method,n_pairs=len(g),step_sd_nm=step,
            mean_nominal_abs_error_nm=float(g.nominal_abs_error_nm.mean()),median_within_grid_sd_nm=float(g.within_grid_sd_nm.median()),median_cross_axis_abs_nm=float(g.cross_axis_abs_nm.median()),
            p95_nominal_abs_error_nm=float(g.nominal_abs_error_nm.quantile(.95)),max_nominal_abs_error_nm=float(g.nominal_abs_error_nm.max()),max_cross_axis_abs_nm=float(g.cross_axis_abs_nm.max()))
    for method,g in t.groupby('method',sort=False):
        for seq,sg in g.groupby('sequence',sort=False):rows.append(one(method,seq,sg,'per_sequence'))
        rows.append(one(method,'combined',g,'all_four_sequences'))
    return pd.DataFrame(rows)


def main():
    out=ROOT/'results/lsc_comparison';p=load(out/'plan.json');config=load(str(PROJECT_ROOT / p['configuration']['path']));locked=pd.read_csv(out/'locked_pairs.csv')
    assert load(out/'R61_reproduction.json')['all_exact'];inf=load(out/'inference_complete.json');assert len(inf['outputs'])==159
    assert all(sha(str(PROJECT_ROOT / s['path']))==s['sha256'] for s in p['sources'])
    methods=['Raw','R61v16_PSFOFF','R128_P_s1285002','R128_no_FOV_guard_diagnostic'];all_pairs=[];checkrows=[];fitrows=[]
    numeric=['aggregate_dx_um','aggregate_dy_um','measured_step_um','nominal_abs_error_nm','within_grid_sd_nm','cross_axis_abs_nm'];keys=['sequence','start_frame_index','end_frame_index','method']
    full_context=pd.read_csv(out/'source_boundary_context.csv')
    for method in methods:
        folder=out/'measurements'/method;done=load(folder/'complete.json');assert done['frames']==159 and done['center_rows']==1431 and done['pair_rows']==120
        centers=pd.read_csv(folder/'centers.csv');assert len(centers)==1431 and not centers.duplicated(['sequence','frame_index','pillar_id']).any()
        assert np.isfinite(centers[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']].to_numpy()).all()
        computed=independent_pairs(centers,locked,config,method);reported=pd.read_csv(folder/'per_pair.csv')
        merged=computed.merge(reported,on=keys,suffixes=('','_saved'),validate='one_to_one');assert len(merged)==120
        errors={key:float((merged[key]-merged[key+'_saved']).abs().max()) for key in numeric};assert max(errors.values())<1e-7
        fits=[]
        for f in p['frames']:
            dest=folder/f['sequence']/f"frame_{f['frame_index']:04d}"
            table=pd.read_csv(dest/'centers.csv').set_index('pillar_id');points=np.load(dest/'boundaries.npz')
            for pid,pts in zip(points['pillar_ids'],points['inflection_points']):
                c=alternate_fit(pts);saved=table.loc[int(pid),['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']].to_numpy(float)
                delta=float(np.max(np.abs(c-saved)));assert delta<1e-4,(method,f['sequence'],f['frame_index'],int(pid),delta)
                fits.append(delta);fitrows.append(dict(method=method,sequence=f['sequence'],frame_index=f['frame_index'],pillar_id=int(pid),max_alternate_fit_difference_px=delta))
        checkrows.append(dict(method=method,centers=len(centers),pairs=len(computed),arithmetic_max_differences=errors,alternate_fit_max_difference_px=max(fits)))
        all_pairs.append(reported)
        print('Verified',method,len(centers),'centers; independent circle fit max',max(fits),flush=True)
    # Independently reconstruct the existing final guard for every native image.
    c=load(ROOT/'config/study.json')['model'];perstep=math.ceil((2*(2+2*sum(c['dilations']))+3)/4)+1;halo=math.ceil((c['iterations']*perstep+2)/16)*16
    output_checks=[]
    for frame in p['frames']:
        rec=load(out/'R128_images'/frame['sequence']/f"frame_{frame['frame_index']:04d}"/'record.json')
        for item in [rec['source'],rec['image'],rec['output_float'],frame['R61']]:assert sha(str(PROJECT_ROOT / item['path']))==item['sha256']
        raw=cv2.imread(str(PROJECT_ROOT / frame['source']['path']),cv2.IMREAD_UNCHANGED).astype(np.float32)/np.float32(255)
        with np.load(rec['output_float']['path']) as f:applied=f['output'];neural=f['neural_output']
        assert applied.shape==neural.shape==raw.shape and np.isfinite(neural).all() and np.isfinite(applied).all()
        h,w=raw.shape;yy,xx=np.ogrid[:h,:w];distance=np.minimum(np.minimum(yy,h-1-yy),np.minimum(xx,w-1-xx)).astype(np.float32);weight=np.clip((distance-halo)/16,0,1)
        expected=raw+(neural-raw)*weight;err=float(np.max(np.abs(expected-applied)));assert err<1e-7
        png=cv2.imread(rec['image']['path'],cv2.IMREAD_UNCHANGED);assert np.array_equal(png,np.rint(applied*255).clip(0,255).astype(np.uint8))
        output_checks.append(dict(sequence=frame['sequence'],frame_index=frame['frame_index'],guard_max_difference=err,PNG_exact=True))
    old=pd.read_csv(str(PROJECT_ROOT / p['historical_pairs']['path']));primary=pd.concat([old,all_pairs[1],all_pairs[2]],ignore_index=True)
    assert len(primary)==840 and primary.method.nunique()==7 and not primary.duplicated(keys).any()
    assert all(len(x)==120 for _,x in primary.groupby('method'))
    expected_pairs=set(map(tuple,locked[keys[:-1]].to_numpy()))
    assert all(set(map(tuple,g[keys[:-1]].to_numpy()))==expected_pairs for _,g in primary.groupby('method'))
    summary=summarize(primary);diagnostic=pd.concat([primary,all_pairs[3]],ignore_index=True)
    diag_summary=summarize(diagnostic)
    pair_context=pd.read_csv(out/'source_boundary_pair_context.csv')
    matched=diagnostic.merge(pair_context,on=keys[:-1],validate='many_to_one')
    inner=summarize(matched[matched.all9_fully_neural])
    a=pd.read_csv(out/'measurements/R128_P_s1285002/centers.csv');b=pd.read_csv(out/'measurements/R128_no_FOV_guard_diagnostic/centers.csv')
    common=a.merge(b,on=['sequence','frame_index','pillar_id'],suffixes=('','_neural')).merge(full_context,on=['sequence','frame_index','pillar_id'])
    full=common[common.patch_fully_neural]
    cols=['lsc_center_x_px','lsc_center_y_px','lsc_radius_px'];guard_parity={k:float((full[k]-full[k+'_neural']).abs().max()) for k in cols};assert max(guard_parity.values())<1e-7
    comparisons=[]
    for baseline in ['Raw','Wiener','R61v16_PSFOFF','R109 E48','R119_B_E42']:
        merged=primary[primary.method=='R128_P_s1285002'].merge(primary[primary.method==baseline],on=keys[:-1],suffixes=('','_baseline'),validate='one_to_one')
        for metric in ['nominal_abs_error_nm','within_grid_sd_nm','cross_axis_abs_nm']:
            change=merged[metric]-merged[metric+'_baseline']
            comparisons.append(dict(baseline=baseline,metric=metric,improved=int((change< -1e-7).sum()),worsened=int((change>1e-7).sum()),tied=int((change.abs()<=1e-7).sum()),median_candidate_minus_baseline_nm=float(change.median())))
    worst=primary[primary.method=='R128_P_s1285002'].merge(primary[primary.method=='R61v16_PSFOFF'],on=keys[:-1],suffixes=('','_R61'),validate='one_to_one')
    worst['nominal_error_increase_vs_R61_nm']=worst.nominal_abs_error_nm-worst.nominal_abs_error_nm_R61
    worst=worst.sort_values('nominal_error_increase_vs_R61_nm',ascending=False)
    outputs={'combined_pairs':primary,'combined_summary':summary,'diagnostic_summary':diag_summary,'fully_neural_subset_summary':inner,'paired_comparisons':pd.DataFrame(comparisons),'worst_pairs_vs_R61':worst,'alternate_circle_fit_checks':pd.DataFrame(fitrows),'output_guard_checks':pd.DataFrame(output_checks)}
    for name,data in outputs.items():
        with (out/(name+'.csv')).open('x',encoding='utf-8',newline='') as f:data.to_csv(f,index=False)
    # Reader identities remain unchanged; execution checkpoints are not retrained.
    for key in ['checkpoint_R128','checkpoint_R61']:assert sha(str(PROJECT_ROOT / p[key]['path']))==p[key]['sha256']
    save(out/'verification.json',dict(verified_utc=now(),source=record(__file__),checks=checkrows,all159_native_outputs_verified=True,all7primary_methods_same120pairs=True,
        all5724_saved_boundary_circles_independently_refitted=True,guard_reconstruction_max=float(max(x['guard_max_difference'] for x in output_checks)),fully_neural_reader_guard_parity=guard_parity,
        Raw_historical_parity=load(out/'measurements/Raw/complete.json')['Raw_historical_parity_max'],R61_reproduction=record(out/'R61_reproduction.json'),original_source_records_unchanged=True,
        frozen_checkpoints_unchanged=True,no_training=True,no_new_confirmation=True,primary_summary=record(out/'combined_summary.csv'),primary_pairs=record(out/'combined_pairs.csv'),plan=record(out/'plan.json')))
    print(summary[summary.scope=='all_four_sequences'].to_string(index=False),flush=True)
    print('Diagnostic only:');print(diag_summary[(diag_summary.scope=='all_four_sequences') & diag_summary.method.str.contains('R128')].to_string(index=False),flush=True)

if __name__=='__main__':main()
