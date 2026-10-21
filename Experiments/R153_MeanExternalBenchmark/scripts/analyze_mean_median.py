"""Reaggregate fixed saved LSC centers; never reconstruct or refit optical data."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import *
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from scipy.stats import skew
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=ROOT/'results/analysis'
TABLES=PUBLIC/'data'
FIGURES=PUBLIC/'figures'
for directory in (OUT,TABLES,FIGURES):directory.mkdir(parents=True,exist_ok=True)


def export(name,rows):
    pd.DataFrame(rows).to_csv(TABLES/name,index=False,encoding='utf-8-sig')


def aggregate_stats(displacements,errors):
    s=displacements.std(axis=1,ddof=1)
    return {'pooled_within_scan_sd_nm':float(np.sqrt(np.mean(s*s))),
            'mean_scan_sd_nm':float(s.mean()),'sd_of_scan_sds_nm':float(s.std(ddof=1)),
            'minimum_scan_sd_nm':float(s.min()),'maximum_scan_sd_nm':float(s.max()),
            'mae_nm':float(np.abs(errors).mean()),'rmse_nm':float(np.sqrt(np.mean(errors**2))),
            'signed_bias_nm':float(errors.mean()),'maximum_absolute_error_nm':float(np.abs(errors).max())}


def error_stats(errors):
    return {'mae_nm':float(np.abs(errors).mean()),'rmse_nm':float(np.sqrt(np.mean(errors**2))),
            'signed_bias_nm':float(errors.mean()),'maximum_absolute_error_nm':float(np.abs(errors).max())}


def source_verification(plan):
    rows=[]
    expected=pd.read_csv(RECORD/'data/verified_measurement_sources.csv')
    for row in expected.itertuples():
        actual=sha(row.path)
        if actual!=row.sha256:raise RuntimeError('Saved readout changed: '+row.path)
        rows.append({'role':row.role,'path':row.path,'sha256':actual})
    for name in ('capture_plan.json','calibration.json','tracking.csv','measurement_config.json'):
        path=MOSR_SOURCE/'evaluation'/name
        copied=RECORD/'sources/evaluation'/name
        if copied.exists():assert sha(path)==sha(copied),name
        rows.append({'role':'frozen_measurement_definition','path':str(path),'sha256':sha(path)})
    for run in plan['runs']:
        position=run['positions']
        assert sha(position['path'])==position['sha256']
        rows.append({'role':'original_PI_positions','path':position['path'],'sha256':position['sha256']})
    pd.DataFrame(rows).to_csv(OUT/'verified_fixed_measurement_sources.csv',index=False,encoding='utf-8-sig')
    return rows


def main():
    plan=read(MOSR_SOURCE/'evaluation/capture_plan.json')
    cal=read(MOSR_SOURCE/'evaluation/calibration.json')
    assert len(plan['runs'])==30 and len(plan['frames'])==930 and cal['nominal_um_per_px']==.1725
    source_rows=source_verification(plan)
    u=np.asarray(cal['axis_unit_vector']);v=np.asarray(cal['transverse_unit_vector'])
    runs=[r['run'] for r in plan['runs']]
    frames={r:sorted([f for f in plan['frames'] if f['run']==r],key=lambda f:f['index']) for r in runs}
    pi=np.array([[f['pi_y_um'] for f in frames[r]] for r in runs],dtype=np.float64)
    pi_adj=np.diff(pi,axis=1)*1000
    pi_start=(pi[:,1:]-pi[:,:1])*1000
    centers={}
    with np.load(RECORD/'data/complete_saved_boundary_points_RAW_R152.npz',allow_pickle=False) as z:
        assert z['run_ids'].tolist()==runs and z['pillar_ids'].tolist()==list(range(1,10))
        for label,key,directory in [('RAW','RAW_centers_px',MOSR_SOURCE/'evaluation/baseline_centers/Raw'),
                                    ('MOSR','R152_centers_px',MOSR_SOURCE/'results/centers')]:
            data=[]
            for run in runs:
                df=pd.read_csv(directory/(run+'.csv')).sort_values(['index','pillar_id'])
                assert len(df)==279 and not df.duplicated(['index','pillar_id']).any()
                assert set(df['index'])==set(range(31)) and set(df.pillar_id)==set(range(1,10))
                data.append(df[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2))
            centers[label]=np.stack(data)
            assert np.array_equal(centers[label],z[key]),label
            assert np.isfinite(centers[label]).all()
    old=pd.read_csv(RECORD/'data/all_displacements_RAW_R152.csv')
    results={};summary=[];scan_rows=[];step_rows=[];pillar_rows=[];position_rows=[];dispersion=[];influences=[];diagnostics=[]
    max_old_difference=0.
    for method,c in centers.items():
        results[method]={}
        deltas={'adjacent':c[:,1:]-c[:,:-1],'start':c[:,1:]-c[:,:1]}
        for aggregation in ('median','mean'):
            result={}
            for kind,delta in deltas.items():
                vector=getattr(np,aggregation)(delta,axis=2)
                image_um=(vector@u)*.1725
                image=image_um*1000
                reference=pi_adj if kind=='adjacent' else pi_start
                errors=image-reference
                result[kind]={'displacement':image,'error':errors,'vector_px':vector}
                if aggregation=='median':
                    label='RAW' if method=='RAW' else 'R152'
                    previous=old[(old.method==label)&(old.kind==kind)].sort_values(['run_index','j'])
                    assert len(previous)==900
                    difference=float(np.max(np.abs(image_um.ravel()-previous.image_displacement_um.to_numpy())))
                    assert difference<1e-12,(method,kind,difference)
                    max_old_difference=max(max_old_difference,difference)
                if kind=='adjacent':
                    stats=aggregate_stats(image,errors)
                    result['scan_sd']=image.std(1,ddof=1)
                    centered=image-image.mean(1,keepdims=True)
                    assert abs(stats['pooled_within_scan_sd_nm']-np.sqrt(np.sum(centered**2)/(30*29)))<1e-12
                else:stats=error_stats(errors)
                summary.append({'method':method,'aggregation':aggregation,'kind':kind,**stats})
                for r,run in enumerate(runs):
                    per={'method':method,'aggregation':aggregation,'kind':kind,'scan':r+1,'run':run,
                         **error_stats(errors[r]),'mean_displacement_nm':float(image[r].mean())}
                    if kind=='adjacent':per['within_scan_sd_nm']=float(image[r].std(ddof=1))
                    scan_rows.append(per)
                    for j in range(30):
                        step_rows.append({'method':method,'aggregation':aggregation,'kind':kind,'scan':r+1,'run':run,
                                          'step':j+1,'start_frame':j if kind=='adjacent' else 0,'end_frame':j+1,
                                          'dx_px':vector[r,j,0],'dy_px':vector[r,j,1],
                                          'displacement_nm':image[r,j],'PI_displacement_nm':reference[r,j],
                                          'error_nm':errors[r,j],'transverse_nm':float(vector[r,j]@v)*SCALE_NM})
                for j in range(30):
                    position_rows.append({'method':method,'aggregation':aggregation,'kind':kind,'step':j+1,
                                           'mean_displacement_nm':float(image[:,j].mean()),
                                           'displacement_sd_nm':float(image[:,j].std(ddof=1)),
                                           'mean_error_nm':float(errors[:,j].mean()),'error_sd_nm':float(errors[:,j].std(ddof=1))})
            ep=result['start']['error'][:,-1]
            result['endpoint']={**error_stats(ep),'error_sd_nm':float(ep.std(ddof=1)),
                                'measured_displacement_sd_nm':float(result['start']['displacement'][:,-1].std(ddof=1)),
                                'mean_measured_displacement_nm':float(result['start']['displacement'][:,-1].mean()),
                                'minimum_error_nm':float(ep.min()),'maximum_error_nm':float(ep.max())}
            if aggregation=='mean':
                assert np.max(np.abs(result['adjacent']['displacement'].cumsum(1)-result['start']['displacement']))<2e-11
            results[method][aggregation]=result
        delta=deltas['adjacent']
        along=(delta@u)*SCALE_NM;cross=(delta@v)*SCALE_NM
        mean=results[method]['mean']['adjacent']['displacement']
        med=results[method]['median']['adjacent']['displacement']
        # Diagnostic flags only: every pillar and every step remains in primary results.
        scalar_med=np.median(along,axis=2,keepdims=True)
        mad=np.median(np.abs(along-scalar_med),axis=2,keepdims=True)
        robust_z=(along-scalar_med)/np.maximum(1.4826*mad,1e-12)
        flags=np.abs(robust_z)>3.5
        skewness=skew(along,axis=2,bias=False)
        signed_contribution=(along-med[...,None])/9
        assert np.max(np.abs(signed_contribution.sum(2)-(mean-med)))<1e-12
        scatter=np.sqrt(np.var(along,axis=2,ddof=1)+np.var(cross,axis=2,ddof=1))
        for r,run in enumerate(runs):
            for j in range(30):
                dispersion.append({'method':method,'scan':r+1,'run':run,'step':j+1,
                                   'along_sample_sd_nm':float(along[r,j].std(ddof=1)),
                                   'transverse_sample_sd_nm':float(cross[r,j].std(ddof=1)),
                                   'vector_sample_scatter_nm':float(scatter[r,j]),
                                   'along_range_nm':float(np.ptp(along[r,j])),
                                   'mean_minus_component_median_nm':float(mean[r,j]-med[r,j]),
                                   'sample_skewness':float(skewness[r,j]),
                                   'diagnostic_MAD_flag_count':int(flags[r,j].sum())})
                for k in range(9):
                    pillar_rows.append({'method':method,'scan':r+1,'run':run,'step':j+1,'pillar':k+1,
                                        'dx_px':delta[r,j,k,0],'dy_px':delta[r,j,k,1],
                                        'along_displacement_nm':along[r,j,k],'transverse_nm':cross[r,j,k],
                                        'PI_error_nm':along[r,j,k]-pi_adj[r,j],
                                        'contribution_to_mean_minus_median_nm':signed_contribution[r,j,k],
                                        'leave_one_out_mean_change_nm':(mean[r,j]-along[r,j,k])/8,
                                        'diagnostic_MAD_flag':bool(flags[r,j,k])})
        for k in range(9):
            without=np.delete(along,k,axis=2).mean(2)
            influences.append({'method':method,'pillar':k+1,
                                'mean_abs_contribution_to_mean_median_nm':float(np.abs(signed_contribution[:,:,k]).mean()),
                                'mean_signed_contribution_nm':float(signed_contribution[:,:,k].mean()),
                                'mean_abs_leave_one_out_change_nm':float(np.abs(without-mean).mean()),
                                'pooled_sd_of_this_pillar_nm':float(np.sqrt(np.mean(along[:,:,k].std(1,ddof=1)**2))),
                                'diagnostic_flag_count':int(flags[:,:,k].sum()),
                                'leave_one_out_pooled_sd_nm':float(np.sqrt(np.mean(without.std(1,ddof=1)**2))),
                                'leave_one_out_PI_MAE_nm':float(np.abs(without-pi_adj).mean())})
        diagnostics.append({'method':method,'steps_with_any_MAD_flag':int(flags.any(2).sum()),
                            'MAD_flagged_pillar_observations':int(flags.sum()),'total_pillar_observations':8100,
                            'median_absolute_step_skewness':float(np.median(np.abs(skewness))),
                            'steps_abs_skewness_over_1':int((np.abs(skewness)>1).sum()),
                            'mean_abs_mean_median_difference_nm':float(np.abs(mean-med).mean()),
                            'maximum_abs_mean_median_difference_nm':float(np.abs(mean-med).max()),
                            'pooled_along_pillar_dispersion_nm':float(np.sqrt(np.mean(along.var(2,ddof=1)))),
                            'pooled_transverse_pillar_dispersion_nm':float(np.sqrt(np.mean(cross.var(2,ddof=1)))),
                            'pooled_vector_pillar_scatter_nm':float(np.sqrt(np.mean(scatter**2)))})
    # Whole-scan paired draws shared by every aggregation and method.
    draw=np.random.default_rng(BOOTSTRAP_SEED).integers(0,30,size=(BOOTSTRAP_DRAWS,30))
    boot={};point={};intervals=[];comparisons=[]
    for method in results:
        for aggregation in results[method]:
            r=results[method][aggregation];s=r['scan_sd'];key=(method,aggregation)
            values={'pooled_within_scan_sd_nm':np.sqrt(np.mean(s[draw]**2,axis=1))}
            estimate={'pooled_within_scan_sd_nm':float(np.sqrt(np.mean(s*s)))}
            for kind in ('adjacent','start'):
                e=r[kind]['error']
                for name,per in [('mae',np.abs(e).mean(1)),('bias',e.mean(1)),('mse',(e*e).mean(1))]:
                    values[kind+'_'+name]=per[draw].mean(1)
                    estimate[kind+'_'+name]=float(per.mean())
            e=r['start']['error'][:,-1]
            values['endpoint_bias']=e[draw].mean(1);estimate['endpoint_bias']=float(e.mean())
            values['endpoint_mae']=np.abs(e[draw]).mean(1);estimate['endpoint_mae']=float(np.abs(e).mean())
            boot[key]=values;point[key]=estimate
    for aggregation in ('mean','median'):
        rs=results['RAW'][aggregation]['scan_sd'];ms=results['MOSR'][aggregation]['scan_sd']
        gains=100*(1-ms/rs)
        comparisons.append({'aggregation':aggregation,'improved_scans':int((ms<rs).sum()),
                            'minimum_scan_improvement_percent':float(gains.min()),'maximum_scan_improvement_percent':float(gains.max()),
                            'pooled_reduction_percent':float(100*(1-np.linalg.norm(ms)/np.linalg.norm(rs)))})
        for metric in boot[('RAW',aggregation)]:
            difference=boot[('MOSR',aggregation)][metric]-boot[('RAW',aggregation)][metric]
            low,high=np.quantile(difference,[.025,.975])
            row={'comparison':'MOSR minus RAW','aggregation':aggregation,'metric':metric,
                 'RAW':point[('RAW',aggregation)][metric],'MOSR':point[('MOSR',aggregation)][metric],
                 'difference':point[('MOSR',aggregation)][metric]-point[('RAW',aggregation)][metric],
                 'paired_CI95_low':float(low),'paired_CI95_high':float(high)}
            if metric in ('pooled_within_scan_sd_nm','adjacent_mae','start_mae'):
                gain=100*(1-boot[('MOSR',aggregation)][metric]/boot[('RAW',aggregation)][metric])
                row.update(reduction_percent=100*(1-row['MOSR']/row['RAW']),
                           reduction_CI95_low=float(np.quantile(gain,.025)),reduction_CI95_high=float(np.quantile(gain,.975)))
            intervals.append(row)
    for method in results:
        for metric in boot[(method,'mean')]:
            samples=boot[(method,'mean')][metric]-boot[(method,'median')][metric]
            low,high=np.quantile(samples,[.025,.975])
            intervals.append({'comparison':'mean minus median','method':method,'metric':metric,
                              'difference':point[(method,'mean')][metric]-point[(method,'median')][metric],
                              'paired_CI95_low':float(low),'paired_CI95_high':float(high)})
    paired=[]
    for i,run in enumerate(runs):
        row={'scan':i+1,'run':run}
        for method in results:
            for agg in ('mean','median'):
                r=results[method][agg]
                row[f'{method}_{agg}_SD_nm']=float(r['scan_sd'][i])
                row[f'{method}_{agg}_adjacent_MAE_nm']=float(np.abs(r['adjacent']['error'][i]).mean())
                row[f'{method}_{agg}_endpoint_error_nm']=float(r['start']['error'][i,-1])
            row[f'{method}_mean_minus_median_SD_nm']=row[f'{method}_mean_SD_nm']-row[f'{method}_median_SD_nm']
        row['mean_SD_improvement_percent']=100*(1-row['MOSR_mean_SD_nm']/row['RAW_mean_SD_nm'])
        paired.append(row)
    export('aggregation_summary.csv',summary);export('per_scan_metrics.csv',scan_rows)
    export('all_aggregated_displacements.csv',step_rows);export('all_pillar_displacements.csv',pillar_rows)
    export('per_step_across_scan_statistics.csv',position_rows);export('nine_pillar_dispersion.csv',dispersion)
    export('pillar_influence_diagnostics.csv',influences);export('distribution_diagnostics.csv',diagnostics)
    export('mean_median_paired_intervals.csv',intervals);export('paired_30_scan_comparison.csv',paired)
    export('endpoint_summary.csv',[{'method':m,'aggregation':a,**r['endpoint']} for m,d in results.items() for a,r in d.items()])
    payload={f'{m}_{a}_{k}_{field}':value for m,d in results.items() for a,r in d.items()
             for k in ('adjacent','start') for field,value in r[k].items()}
    payload.update(run_ids=np.array(runs),PI_positions_um=pi,axis_unit_vector=u,transverse_unit_vector=v,
                   **{f'{m}_centers_px':c for m,c in centers.items()})
    np.savez_compressed(OUT/'fixed_center_reaggregation.npz',**payload)
    output={'status':'passed','published_median_max_difference_um':max_old_difference,
            'source_files_verified':len(source_rows),'optical_circle_refits':0,'MOSR_reconstructions':0,
            'primary_aggregation':'mean_of_nine_2D_vectors_then_fixed_projection',
            'summary':summary,'comparison':comparisons,'diagnostics':diagnostics,
            'endpoints':[{'method':m,'aggregation':a,**r['endpoint']} for m,d in results.items() for a,r in d.items()],
            'bootstrap':{'draws':BOOTSTRAP_DRAWS,'seed':BOOTSTRAP_SEED,'unit':'whole paired scan'},
            'all_30_scans_and_all_nine_pillars_retained':True}
    save(OUT/'mean_median_complete.json',output)
    plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],
                         'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'savefig.bbox':'tight','svg.fonttype':'none'})
    fig,ax=plt.subplots(figsize=(7.2,3.5))
    for method,color,marker,style in [('RAW','0.55','o','--'),('MOSR','0','s','-')]:
        s=results[method]['mean']['scan_sd'];avg=s.mean();sd=s.std(ddof=1)
        ax.axhspan(avg-sd,avg+sd,color=color,alpha=.1)
        ax.plot(np.arange(1,31),s,color=color,marker=marker,linestyle=style,markersize=3,
                markerfacecolor='white',label=f'{method}: {avg:.3f} ± {sd:.3f} nm')
    ax.set(xlabel='Repeated scan number',ylabel='Within-scan step SD (nm)',xlim=(.5,30.5),ylim=(0,None))
    ax.legend(frameon=False,ncol=2);ax.grid(axis='y',color='.9',linewidth=.5)
    fig.tight_layout()
    for suffix in ('png','svg'):fig.savefig(FIGURES/f'mean_within_scan_sd.{suffix}',dpi=300)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(7.2,3.2),sharey=True)
    for ax,method in zip(axes,('RAW','MOSR')):
        for agg,color,marker,style in [('median','.6','o','--'),('mean','0','s','-')]:
            ax.plot(np.arange(1,31),results[method][agg]['scan_sd'],color=color,marker=marker,
                    linestyle=style,markersize=2.6,markerfacecolor='white',label=agg)
        ax.set(title=method,xlabel='Scan number');ax.legend(frameon=False);ax.grid(axis='y',color='.9',linewidth=.5)
    axes[0].set_ylabel('Within-scan step SD (nm)');fig.tight_layout()
    for suffix in ('png','svg'):fig.savefig(FIGURES/f'mean_median_sensitivity.{suffix}',dpi=300)
    plt.close(fig)
    print(json.dumps(output,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
