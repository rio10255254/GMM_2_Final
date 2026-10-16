"""Independently recompute the ten-method thesis tables from saved point observations.

Inputs contain the full 30 scans, 31 frames and nine objects for every method.
This recalculates measurements/statistics; it does not refit contours, execute a
model, select a checkpoint, or claim an independent physical accuracy result.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import numpy as np
import pandas as pd


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def metrics(centers, diameters, points, pi, axis, scale, draws, weights, sem):
    theta=np.linspace(0,2*np.pi,720,endpoint=False)
    radial=[]
    for boundary,center in zip(points.reshape(-1,64,2),centers.reshape(-1,2)):
        delta=boundary-center
        radial.append(np.interp(theta,np.arctan2(delta[:,1],delta[:,0]),
                                np.hypot(delta[:,0],delta[:,1]),period=2*np.pi))
    radial=np.asarray(radial).reshape(30,31,9,720)*scale
    shape=radial-radial.mean(-1,keepdims=True)
    values={'valid_scans':30,'mean_diameter_nm':float(diameters.mean()),
            'maximum_diameter_deviation_nm':float(abs(diameters-diameters.mean(0)).max())}
    bootstrap={}
    for name,data in [('diameter_repeat_sd_nm',diameters),('contour_repeat_sd_nm',radial),('shape_repeat_sd_nm',shape)]:
        values[name]=float(np.sqrt(np.var(data,axis=0,ddof=1).mean()))
        flat=data.reshape(30,-1);flat=flat-flat.mean(0)
        gram=flat@flat.T/flat.shape[1]
        variance=(weights@np.diag(gram)-np.sum((weights@gram)*weights,axis=1))*30/29
        bootstrap[name]=np.sqrt(np.maximum(variance,0))
    displacement={}
    for kind,delta,reference in [('adjacent',np.diff(centers,axis=1),np.diff(pi,axis=1)*1000),
                                 ('start',centers[:,1:]-centers[:,:1],(pi[:,1:]-pi[:,:1])*1000)]:
        distance=(delta.mean(2)@axis)*scale;error=distance-reference
        displacement[kind]=(distance,error,reference)
        for key,a in [('mae',abs(error).mean(1)),('rmse',(error**2).mean(1)),('bias',error.mean(1))]:
            name=kind+'_'+key+'_nm';sample=a[draws].mean(1)
            values[name]=float(np.sqrt(a.mean()) if key=='rmse' else a.mean())
            bootstrap[name]=np.sqrt(sample) if key=='rmse' else sample
        values[kind+'_maximum_abs_error_nm']=float(abs(error).max())
        if kind=='adjacent':
            sd=distance.std(1,ddof=1)
            values['pooled_within_scan_sd_nm']=float(np.sqrt(np.mean(sd**2)))
            values['mean_scan_sd_nm']=float(sd.mean())
            values['sd_of_scan_sds_nm']=float(sd.std(ddof=1))
            bootstrap['pooled_within_scan_sd_nm']=np.sqrt((sd[draws]**2).mean(1))
        else:
            endpoint=error[:,-1]
            values['endpoint_rmse_nm']=float(np.sqrt((endpoint**2).mean()))
            values['endpoint_error_sd_nm']=float(endpoint.std(ddof=1))
            for label,a in [('bias',endpoint),('mae',abs(endpoint))]:
                name='endpoint_'+label+'_nm';values[name]=float(a.mean());bootstrap[name]=a[draws].mean(1)
    for label,reference in [('SEM_workbook',sem['workbook_diameter_nm']),('SEM_contour',sem['contour_diameter_nm'])]:
        key=label+'_diameter_MAE_nm'
        values[key]=float(abs(diameters.mean((0,1))-reference).mean())
        bootstrap[key]=abs(weights@diameters.mean(1)-reference).mean(1)
    for i,reference in enumerate(sem['radial_candidates_nm'],1):
        for label,error in [('full_radial_difference_nm',abs(radial-reference)),
                            ('de_size_shape_difference_nm',abs(shape-(reference-reference.mean(-1,keepdims=True))))]:
            key=f'SEM_candidate{i}_'+label
            values[key]=float(error.mean());bootstrap[key]=weights@error.mean((1,2,3))
    return values,bootstrap,displacement


def replay(root, spec_path, output):
    if output.exists():raise FileExistsError('Use a new result directory; historical results are never overwritten')
    spec=json.loads(spec_path.read_text(encoding='utf-8-sig'))
    for item in spec['files']:
        p=root/item['path']
        if sha(p)!=item['sha256']:raise ValueError('Replay input changed: '+item['path'])
    output.mkdir(parents=True)
    start=time.perf_counter();expected=pd.read_csv(root/spec['summary']).set_index('method')
    published=pd.read_csv(root/spec['displacements'])
    intervals=pd.read_csv(root/spec['intervals'])
    draws=np.random.default_rng(spec['bootstrap_seed']).integers(0,30,size=(spec['bootstrap_draws'],30))
    weights=np.stack([np.bincount(row,minlength=30) for row in draws])/30
    all_values={};all_boot={};maximum_metric_error=0.;maximum_displacement_error=0.;checked_metrics=0;checked_displacements=0
    with np.load(root/spec['observations'],allow_pickle=False) as data:
        methods=data['methods'].tolist();assert len(methods)==10 and set(methods)==set(expected.index)
        pi=data['PI_positions_um'];axis=data['axis_unit_vector'];scale=float(data['nm_per_pixel'])
        assert pi.shape==(30,31) and abs(np.linalg.norm(axis)-1)<1e-12 and scale==172.5
        sem={k:data['SEM_'+k] for k in ['workbook_diameter_nm','contour_diameter_nm','radial_candidates_nm']}
        for i,method in enumerate(methods):
            centers=data['centers_px'][i];diameters=data['diameters_nm'][i];points=data['points_px'][i]
            assert centers.shape==(30,31,9,2) and points.shape==(30,31,9,64,2) and diameters.shape==(30,31,9)
            assert all(np.isfinite(a).all() for a in [centers,diameters,points])
            values,boot,distances=metrics(centers,diameters,points,pi,axis,scale,draws,weights,sem)
            for key,value in values.items():
                difference=abs(value-float(expected.loc[method,key]));maximum_metric_error=max(maximum_metric_error,difference)
                if difference>1e-7:raise ValueError(f'Published metric mismatch: {method}/{key}: {difference}')
                checked_metrics+=1
            for kind,(distance,error,reference) in distances.items():
                rows=published[(published.method==method)&(published.kind==kind)].sort_values(['scan','step'])
                assert len(rows)==900 and not rows.duplicated(['scan','step']).any()
                for name,actual in [('displacement_nm',distance),('error_nm',error),('PI_displacement_nm',reference)]:
                    difference=float(np.max(abs(rows[name].to_numpy()-actual.ravel())))
                    maximum_displacement_error=max(maximum_displacement_error,difference)
                    if difference>1e-7:raise ValueError(f'Published displacement mismatch: {method}/{kind}/{name}')
                checked_displacements+=len(rows)
            all_values[method]=values;all_boot[method]=boot
            print('INDEPENDENTLY_RECALCULATED',method,flush=True)
    maximum_interval_error=0.;new_intervals=[]
    for row in intervals.itertuples():
        reference=row.reference_method;key=row.metric
        difference=all_values['MOSR'][key]-all_values[reference][key]
        interval=np.quantile(all_boot['MOSR'][key]-all_boot[reference][key],[.025,.975])
        delta=max(abs(difference-row.difference),float(np.max(abs(interval-[row.CI95_low,row.CI95_high]))))
        maximum_interval_error=max(maximum_interval_error,delta)
        if delta>1e-7:raise ValueError(f'Published complete-scan interval mismatch: {reference}/{key}')
        new_intervals.append({'reference_method':reference,'metric':key,'difference':difference,'CI95_low':interval[0],'CI95_high':interval[1]})
    assert checked_displacements==18000 and len(new_intervals)==162
    frame=pd.DataFrame([{'method':m,**all_values[m]} for m in methods])
    frame.to_csv(output/'recomputed_summary.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(new_intervals).to_csv(output/'recomputed_paired_intervals.csv',index=False,encoding='utf-8-sig')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(15,4.5))
    for ax,key,title in zip(axes,['pooled_within_scan_sd_nm','adjacent_mae_nm','diameter_repeat_sd_nm'],
                           ['Within-scan step SD','Adjacent PI absolute difference','Diameter repeat SD']):
        ax.bar(np.arange(len(methods)),frame[key],color=['black' if m=='MOSR' else '0.65' for m in methods])
        ax.set_xticks(np.arange(len(methods)),methods,rotation=65,ha='right');ax.set_ylabel('nm');ax.set_title(title)
    fig.tight_layout();fig.savefig(output/'recomputed_primary_results.png',dpi=180);plt.close(fig)
    report={'status':'PASS','methods':methods,'scans_per_method':30,'photographs_per_method':930,
            'object_readouts_per_method':8370,'independent_numeric_metrics_checked':checked_metrics,
            'independent_displacements_checked':checked_displacements,'complete_scan_paired_intervals_checked':len(new_intervals),
            'maximum_metric_difference_nm':maximum_metric_error,'maximum_displacement_difference_nm':maximum_displacement_error,
            'maximum_interval_difference_nm':maximum_interval_error,'bootstrap_draws':spec['bootstrap_draws'],
            'resampling_unit':'complete scan','saved_point_measurements_are_inputs':True,'new_model_inferences':0,
            'new_contour_refits':0,'unfavorable_size_and_long_distance_results_retained':True,'seconds':time.perf_counter()-start}
    (output/'REPLAY_VERIFIED.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--spec',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();replay(a.root,a.spec,a.output)
