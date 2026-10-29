"""Recompute complete paired RAW/R152 measurement statistics from saved readouts."""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import statistics
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
PROJECT_ROOT = Path(__file__).resolve().parents[4]

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
MODELS = {"RAW": "Raw", "R152": "R152-R148v2-SafeAdaptivePSF"}
ANGLES = np.linspace(0, 2*np.pi, 720, endpoint=False)
SCALE = 172.5
DRAW_COUNT, SEED = 20000, 20261002

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(8*1024*1024), b""):h.update(b)
    return h.hexdigest()

def radius_profile(points, center):
    q = points-center
    a = np.mod(np.arctan2(q[:,1],q[:,0]), 2*np.pi)
    r = np.linalg.norm(q,axis=1)
    ix = np.argsort(a); a,r = a[ix],r[ix]
    return np.interp(ANGLES,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[r[-1],r,r[0]])

def export(name, rows):
    pd.DataFrame(rows).to_csv(OUT/name,index=False,encoding="utf-8-sig")

def check_artifacts(plan):
    checks=[]
    lock=read(ROOT/'config/SOURCE_LOCK.json')
    for relative,expected in lock['files'].items():
        actual=digest(ROOT/relative);assert actual==expected,(relative,actual,expected)
        checks.append(dict(role='locked_source',path=str(ROOT/relative),sha256=actual))
    complete=read(ROOT/'runs/formal_8192/training_complete.json')
    for role in ('training_checkpoint','deployed_checkpoint'):
        receipt=complete[role];actual=digest(str(PROJECT_ROOT / receipt['path']));assert actual==receipt['sha256']
        checks.append(dict(role=role,path=str(PROJECT_ROOT / receipt['path']),sha256=actual))
    base=read(ROOT/'config/model.json');assert digest(str(PROJECT_ROOT / base['base_checkpoint']))==base['base_checkpoint_sha256']
    tasks=[]
    for f in plan['frames']:
        receipt_path=ROOT/'results/reconstruction'/f['run']/f"{f['index']+1:02d}.json"
        receipt=read(receipt_path)
        assert receipt['checkpoint_sha256']==complete['deployed_checkpoint']['sha256']
        assert receipt['shape']==[1544,2064] and receipt['deployment_scale']==1
        assert receipt['source']['sha256']==f['source']['sha256']
        tasks.extend([('capture',Path(f['source']['path']),f['source']['sha256']),
                      ('R152_native_output',Path(receipt['output_path']),receipt['output_sha256'])])
    def check(task):
        role,path,expected=task;actual=digest(path);assert actual==expected,str(path)
        return dict(role=role,path=str(path),sha256=actual)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,result in enumerate(pool.map(check,tasks),1):
            checks.append(result)
            if i%300==0:print('HASH',i,'/',len(tasks),flush=True)
    export('verified_source_artifacts.csv',checks)
    return {'source_lock_files':len(lock['files']),'raw_frames_hashed':930,
            'R152_native_outputs_hashed':930,'checkpoint_hashes_match':True,'all_checks_passed':True}

def boot_repeat_sd(values,weights):
    x=values.reshape(30,-1)
    x=x-x.mean(axis=0)
    gram=x@x.T/x.shape[1]
    v=weights@np.diag(gram)-np.sum((weights@gram)*weights,axis=1)
    return np.sqrt(np.maximum(v,0)*30/29)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    plan,cal=read(ROOT/'evaluation/capture_plan.json'),read(ROOT/'evaluation/calibration.json')
    assert read(ROOT/'results/final_audit.json')['passed'] and len(plan['runs'])==30 and len(plan['frames'])==930
    u,t=np.array(cal['axis_unit_vector']),np.array(cal['transverse_unit_vector'])
    assert abs(cal['nominal_um_per_px']-.1725)<1e-14
    integrity=check_artifacts(plan)
    frame_by_run={r['run']:sorted([f for f in plan['frames'] if f['run']==r['run']],key=lambda f:f['index']) for r in plan['runs']}
    arrays={};drows=[];circle_rows=[];center_sources=[]
    for label,model in MODELS.items():
        directory=ROOT/'results/centers' if label=='R152' else ROOT/'evaluation/baseline_centers/Raw'
        ds,ps,cs,pts=[],[],[],[]
        for run in plan['runs']:
            name=run['run'];path=directory/(name+'.csv');df=pd.read_csv(path).sort_values(['index','pillar_id'])
            assert len(df)==279 and not df.duplicated(['index','pillar_id']).any() and set(df.model)=={model}
            assert set(df['index'])==set(range(31)) and set(df.pillar_id)==set(range(1,10))
            with np.load(directory/(name+'.npz'),allow_pickle=False) as z:points=z['points'].astype(np.float64)
            assert points.shape==(31,9,64,2) and np.isfinite(points).all()
            centers=df[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2)
            diameter=2*df.radius_px.to_numpy().reshape(31,9)*SCALE
            profile=np.array([radius_profile(p,c) for p,c in zip(points.reshape(-1,64,2),centers.reshape(-1,2))]).reshape(31,9,720)*SCALE
            frames=frame_by_run[name]
            for kind in ('adjacent','start'):
                for j in range(1,31):
                    i=j-1 if kind=='adjacent' else 0
                    delta=centers[j]-centers[i];med=np.median(delta,axis=0)
                    pi=frames[j]['pi_y_um']-frames[i]['pi_y_um'];observed=float(med@u)*.1725
                    drows.append(dict(method=label,model=model,run=name,run_index=run['run_index'],kind=kind,i=i,j=j,
                                      PI_displacement_um=pi,image_displacement_um=observed,error_nm=1000*(observed-pi),
                                      dx_px=med[0],dy_px=med[1],transverse_nm=float(med@t)*SCALE))
            df['method']=label;df['diameter_nm']=diameter.ravel();circle_rows.append(df)
            ds.append(diameter);ps.append(profile);cs.append(centers);pts.append(points)
            center_sources.extend([dict(role=label+'_centers',path=str(path),sha256=digest(path)),
                                   dict(role=label+'_boundary_points',path=str(directory/(name+'.npz')),sha256=digest(directory/(name+'.npz')))])
        arrays[label]={'diameter':np.array(ds),'profile':np.array(ps),'center':np.array(cs),'points':np.array(pts)}
        print('READOUTS',label,30,'scans',flush=True)
    export('verified_measurement_sources.csv',center_sources)
    d=pd.DataFrame(drows);circles=pd.concat(circle_rows,ignore_index=True)
    assert len(d)==3600 and len(circles)==16740
    export('all_displacements_RAW_R152.csv',drows)
    circles.to_csv(OUT/'all_circles_RAW_R152.csv',index=False,encoding='utf-8-sig')
    # Parity with historical measurement arithmetic is checked, not assumed.
    old=pd.read_csv(ROOT/'results/comparison/all_displacements.csv')
    parity=0
    for label,model in MODELS.items():
        keys=['run','kind','i','j']
        actual=d[d.method==label].sort_values(keys).reset_index(drop=True)
        expected=old[old.model==model].sort_values(keys).reset_index(drop=True)
        assert actual[keys].equals(expected[keys])
        delta=float(np.abs(actual.image_displacement_um-expected.image_displacement_um).max())
        assert delta<1e-12;parity=max(parity,delta)
    rng=np.random.default_rng(SEED);draw=rng.integers(0,30,size=(DRAW_COUNT,30))
    weights=np.array([np.bincount(x,minlength=30)/30 for x in draw])
    summary=[];scan_rows=[];positions=[];boot={};step_arrays={};per_sd={}
    for label in MODELS:
        for kind in ('adjacent','start'):
            g=d[(d.method==label)&(d.kind==kind)]
            image=g.pivot(index='run_index',columns='j',values='image_displacement_um').sort_index().to_numpy()*1000
            errors=g.pivot(index='run_index',columns='j',values='error_nm').sort_index().to_numpy()
            assert image.shape==errors.shape==(30,30)
            mean_error=errors.mean(axis=1);mean_abs=np.abs(errors).mean(axis=1)
            sds=image.std(axis=1,ddof=1)
            for row in image:assert abs(np.std(row,ddof=1)-statistics.stdev(row))<1e-10
            pooled=float(np.sqrt(np.mean(sds*sds)))
            assert abs(pooled-np.sqrt(((image-image.mean(axis=1,keepdims=True))**2).sum()/(30*29)))<1e-10
            metric=dict(method=label,kind=kind,mae_nm=float(mean_abs.mean()),bias_nm=float(errors.mean()),
                        rmse_nm=float(np.sqrt(np.mean(errors**2))),maximum_abs_error_nm=float(np.abs(errors).max()),
                        across_scan_same_step_mean_error_sd_nm=float(errors.std(axis=0,ddof=1).mean()))
            summary.append(metric)
            boot[(label,kind+'_mae_nm')]=mean_abs[draw].mean(1)
            if kind=='adjacent':
                step_arrays[label]=image;per_sd[label]=sds
                boot[(label,'pooled_within_scan_sd_nm')]=np.sqrt(np.mean(sds[draw]**2,axis=1))
                boot[(label,'mean_scan_sd_nm')]=sds[draw].mean(axis=1)
            for ix,run in enumerate(plan['runs']):
                scan_rows.append(dict(method=label,run_index=run['run_index'],run=run['run'],kind=kind,
                                      mae_nm=float(mean_abs[ix]),bias_nm=float(mean_error[ix]),
                                      mean_observed_displacement_nm=float(image[ix].mean()),
                                      within_scan_sd_nm=float(sds[ix]) if kind=='adjacent' else None,
                                      PI_corrected_within_scan_sd_nm=float(errors[ix].std(ddof=1)) if kind=='adjacent' else None,
                                      endpoint_error_nm=float(errors[ix,-1]) if kind=='start' else None))
            for j in range(30):
                observed_sd=float(image[:,j].std(ddof=1));mean=float(image[:,j].mean())
                positions.append(dict(method=label,kind=kind,step=j+1,n_scans=30,
                                      mean_measured_displacement_nm=mean,measured_sd_nm=observed_sd,
                                      measured_lower_nm=mean-observed_sd,measured_upper_nm=mean+observed_sd,
                                      mean_error_nm=float(errors[:,j].mean()),error_sd_nm=float(errors[:,j].std(ddof=1)),
                                      mean_PI_displacement_um=float(g[g.j==j+1].PI_displacement_um.mean())))
    export('displacement_summary_RAW_R152.csv',summary)
    export('per_scan_displacement_RAW_R152.csv',scan_rows)
    export('per_step_statistics_RAW_R152.csv',positions)
    geometry=[];pillar_rows=[];diameter_positions=[];geom_keys=['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm']
    for label,values in arrays.items():
        di,p=values['diameter'],values['profile'];shape=p-p.mean(-1,keepdims=True)
        geo=dict(method=label,mean_diameter_nm=float(di.mean()),
                 diameter_repeat_sd_nm=float(np.sqrt(di.var(axis=0,ddof=1).mean())),
                 contour_repeat_sd_nm=float(np.sqrt(p.var(axis=0,ddof=1).mean())),
                 shape_repeat_sd_nm=float(np.sqrt(shape.var(axis=0,ddof=1).mean())),
                 maximum_diameter_deviation_nm=float(np.abs(di-di.mean(axis=0)).max()),
                 mean_radial_fit_rms_nm=float(circles[circles.method==label].radial_rms_px.mean()*SCALE),
                 median_edge_gradient=float(circles[circles.method==label].gradient_median.median()))
        geometry.append(geo)
        for key,a in zip(geom_keys,(di,p,shape)):boot[(label,key)]=boot_repeat_sd(a,weights)
        for pillar in range(9):
            pillar_rows.append(dict(method=label,pillar_id=pillar+1,mean_diameter_nm=float(di[:,:,pillar].mean()),
                                    diameter_repeat_sd_nm=float(np.sqrt(di[:,:,pillar].var(axis=0,ddof=1).mean())),
                                    contour_repeat_sd_nm=float(np.sqrt(p[:,:,pillar].var(axis=0,ddof=1).mean())),
                                    shape_repeat_sd_nm=float(np.sqrt(shape[:,:,pillar].var(axis=0,ddof=1).mean()))))
        for j in range(31):
            means=di[:,j].mean(axis=1)
            diameter_positions.append(dict(method=label,frame_index=j,mean_of_nine_diameters_nm=float(means.mean()),
                                            across_scan_sd_of_nine_mean_nm=float(means.std(ddof=1)),
                                            pooled_pillar_diameter_sd_nm=float(np.sqrt(di[:,j].var(axis=0,ddof=1).mean()))))
    oldgeom=pd.read_csv(ROOT/'results/comparison/shape_size_summary.csv')
    for g in geometry:
        row=oldgeom[oldgeom.model==MODELS[g['method']]].iloc[0]
        for k in geom_keys:assert abs(g[k]-row[k])<1e-7,(k,g[k],row[k])
    export('geometry_summary_RAW_R152.csv',geometry)
    export('per_pillar_geometry_RAW_R152.csv',pillar_rows)
    export('diameter_by_position_RAW_R152.csv',diameter_positions)
    np.savez_compressed(OUT/'complete_saved_boundary_points_RAW_R152.npz',
                        RAW_points_px=arrays['RAW']['points'],R152_points_px=arrays['R152']['points'],
                        RAW_centers_px=arrays['RAW']['center'],R152_centers_px=arrays['R152']['center'],
                        RAW_diameters_nm=arrays['RAW']['diameter'],R152_diameters_nm=arrays['R152']['diameter'],
                        run_ids=np.array([r['run'] for r in plan['runs']]),pillar_ids=np.arange(1,10))
    mapping=read(ROOT/'evaluation/sem_mapping_candidates.json');sem_scale=read(ROOT/'evaluation/sem_scale.json')['scale_nm_per_px']
    truth={};reference_diam={}
    with np.load(ROOT/'evaluation/sem_points.npz',allow_pickle=False) as z:
        for pid in sorted(mapping[0]['sem_ids_by_new_nine']):
            q=z[f'SEM_{pid}'];q=q-q.mean(0)
            def residual(c):
                r=np.linalg.norm(q-c,axis=1);return r-r.mean()
            c=least_squares(residual,[0.,0.],xtol=1e-12,ftol=1e-12,gtol=1e-12).x
            truth[pid]=(q-c)*sem_scale;reference_diam[pid]=float(2*np.linalg.norm(truth[pid],axis=1).mean())
    sem_rows=[]
    for mi,m in enumerate(mapping,1):
        reference=[]
        for pid in m['sem_ids_by_new_nine']:
            q=truth[pid].copy()
            if m['candidate']['flip']:q[:,0]*=-1
            for _ in range(m['candidate']['k']):q=np.c_[q[:,1],-q[:,0]]
            reference.append(radius_profile(q,np.zeros(2)))
        reference=np.array(reference)
        for label,a in arrays.items():
            p=a['profile']
            sem_rows.append(dict(method=label,mapping_candidate=mi,
                                 full_radial_difference_nm=float(np.abs(p-reference).mean()),
                                 de_size_shape_difference_nm=float(np.abs((p-p.mean(-1,keepdims=True))-
                                                                            (reference-reference.mean(-1,keepdims=True))).mean())))
    current_map=pd.read_csv(ROOT/'evaluation/sem_current_center9_mapping.csv').sort_values(['image_row','image_col'])
    assert current_map.sem_id_working.tolist()==[36,35,34,30,29,28,24,23,22]
    references={'SEM_workbook':current_map.sem_diameter_nm.to_numpy(),
                'SEM_contour':np.array([reference_diam[int(i)] for i in current_map.sem_id_working])}
    sem_size=[];sem_pillars=[]
    for ref_name,ref in references.items():
        for label,a in arrays.items():
            observed=a['diameter'].mean(axis=(0,1));difference=observed-ref
            sem_size.append(dict(method=label,reference=ref_name,reference_mean_diameter_nm=float(ref.mean()),
                                 measured_mean_diameter_nm=float(observed.mean()),mean_signed_difference_nm=float(difference.mean()),
                                 mean_absolute_pillar_difference_nm=float(np.abs(difference).mean()),
                                 maximum_absolute_pillar_difference_nm=float(np.abs(difference).max())))
            for i,row in enumerate(current_map.itertuples()):
                sem_pillars.append(dict(method=label,reference=ref_name,pillar_id=i+1,SEM_id=int(row.sem_id_working),
                                        reference_diameter_nm=float(ref[i]),observed_diameter_nm=float(observed[i]),
                                        signed_difference_nm=float(difference[i])))
    export('SEM_shape_RAW_R152.csv',sem_rows);export('SEM_size_summary_RAW_R152.csv',sem_size)
    export('SEM_size_by_pillar_RAW_R152.csv',sem_pillars)
    # Paired whole-scan intervals; angle and pillar observations never become resampling units.
    per_metrics={g['method']:g for g in geometry}
    within=[];gains=100*(1-per_sd['R152']/per_sd['RAW'])
    for label in MODELS:
        v=per_sd[label];within.append(dict(method=label,mean_scan_sd_nm=float(v.mean()),median_scan_sd_nm=float(np.median(v)),
                                          sd_of_scan_sds_nm=float(v.std(ddof=1)),pooled_within_scan_sd_nm=float(np.sqrt((v*v).mean())),
                                          minimum_nm=float(v.min()),maximum_nm=float(v.max()),
                                          first6_pooled_sd_nm=float(np.sqrt((v[:6]**2).mean())),
                                          later24_pooled_sd_nm=float(np.sqrt((v[6:]**2).mean()))))
    within_map={r['method']:r for r in within}
    intervals=[]
    for key in ('pooled_within_scan_sd_nm','mean_scan_sd_nm','adjacent_mae_nm','start_mae_nm',*geom_keys):
        samples=boot[('R152',key)]-boot[('RAW',key)]
        if key in within_map['RAW']:raw,value=within_map['RAW'][key],within_map['R152'][key]
        elif key.endswith('mae_nm'):
            kind=key.split('_')[0];raw=next(r['mae_nm'] for r in summary if r['method']=='RAW' and r['kind']==kind)
            value=next(r['mae_nm'] for r in summary if r['method']=='R152' and r['kind']==kind)
        else:raw,value=per_metrics['RAW'][key],per_metrics['R152'][key]
        low,high=np.quantile(samples,[.025,.975])
        gain_samples=100*(1-boot[('R152',key)]/boot[('RAW',key)])
        intervals.append(dict(metric=key,RAW_nm=raw,R152_nm=value,R152_minus_RAW_nm=value-raw,
                               difference_CI95_low_nm=float(low),difference_CI95_high_nm=float(high),
                               reduction_percent=float(100*(1-value/raw)),
                               reduction_CI95_low_percent=float(np.quantile(gain_samples,.025)),
                               reduction_CI95_high_percent=float(np.quantile(gain_samples,.975))))
    export('whole_scan_paired_intervals_RAW_R152.csv',intervals)
    paired_scans=[]
    scan_df=pd.DataFrame(scan_rows)
    for i,run in enumerate(plan['runs']):
        record=dict(scan=run['run_index'],run=run['run'],RAW_step_sd_nm=float(per_sd['RAW'][i]),
                    R152_step_sd_nm=float(per_sd['R152'][i]),absolute_sd_reduction_nm=float(per_sd['RAW'][i]-per_sd['R152'][i]),
                    reduction_percent=float(gains[i]))
        for label in MODELS:
            for kind in ('adjacent','start'):
                row=scan_df[(scan_df.method==label)&(scan_df.run==run['run'])&(scan_df.kind==kind)].iloc[0]
                record[f'{label}_{kind}_mae_nm']=float(row.mae_nm)
                if kind=='start':record[f'{label}_endpoint_error_nm']=float(row.endpoint_error_nm)
        paired_scans.append(record)
    export('paired_30_scan_details.csv',paired_scans)
    endpoints=[]
    for label in MODELS:
        endpoint_rows=d[(d.method==label)&(d.kind=='start')&(d.j==30)].sort_values('run_index')
        values=endpoint_rows.error_nm.to_numpy()
        endpoints.append(dict(method=label,mean_signed_error_nm=float(values.mean()),sample_sd_nm=float(values.std(ddof=1)),
                              mae_nm=float(np.abs(values).mean()),minimum_error_nm=float(values.min()),maximum_error_nm=float(values.max()),
                              mean_measured_endpoint_nm=float(endpoint_rows.image_displacement_um.mean()*1000),
                              measured_endpoint_sd_nm=float(endpoint_rows.image_displacement_um.std(ddof=1)*1000),
                              mean_PI_endpoint_nm=float(endpoint_rows.PI_displacement_um.mean()*1000)))
        boot[(label,'endpoint_signed_bias_nm')]=values[draw].mean(1)
        boot[(label,'endpoint_observed_sd_nm')]=(endpoint_rows.image_displacement_um.to_numpy()*1000)[draw].std(axis=1,ddof=1)
    for mi in (1,2):
        m=mapping[mi-1];reference=[]
        for pid in m['sem_ids_by_new_nine']:
            q=truth[pid].copy()
            if m['candidate']['flip']:q[:,0]*=-1
            for _ in range(m['candidate']['k']):q=np.c_[q[:,1],-q[:,0]]
            reference.append(radius_profile(q,np.zeros(2)))
        reference=np.array(reference)
        for label,a in arrays.items():
            p=a['profile']
            full=np.abs(p-reference).mean(axis=(1,2,3))
            shape=np.abs((p-p.mean(-1,keepdims=True))-(reference-reference.mean(-1,keepdims=True))).mean(axis=(1,2,3))
            boot[(label,f'SEM_direction{mi}_full_radial_nm')]=full[draw].mean(1)
            boot[(label,f'SEM_direction{mi}_de_size_shape_nm')]=shape[draw].mean(1)
    for label,a in arrays.items():
        scan_pillar_means=a['diameter'].mean(axis=1)
        boot[(label,'SEM_workbook_mean_absolute_pillar_difference_nm')]=np.abs(weights@scan_pillar_means-references['SEM_workbook']).mean(1)
    extra_intervals=[]
    extra_keys=['endpoint_signed_bias_nm','endpoint_observed_sd_nm','SEM_workbook_mean_absolute_pillar_difference_nm']
    extra_keys += [f'SEM_direction{i}_{metric}_nm' for i in (1,2) for metric in ('full_radial','de_size_shape')]
    for key in extra_keys:
        diff=boot[('R152',key)]-boot[('RAW',key)];low,high=np.quantile(diff,[.025,.975])
        if key.startswith('endpoint'):
            field='mean_signed_error_nm' if key=='endpoint_signed_bias_nm' else 'measured_endpoint_sd_nm'
            values={r['method']:r[field] for r in endpoints}
        elif key.startswith('SEM_workbook'):
            values={r['method']:r['mean_absolute_pillar_difference_nm'] for r in sem_size if r['reference']=='SEM_workbook'}
        else:
            mi=int(key[len('SEM_direction')]);field='full_radial_difference_nm' if 'full_radial' in key else 'de_size_shape_difference_nm'
            values={r['method']:r[field] for r in sem_rows if r['mapping_candidate']==mi}
        extra_intervals.append(dict(metric=key,RAW_nm=values['RAW'],R152_nm=values['R152'],
                                    R152_minus_RAW_nm=values['R152']-values['RAW'],
                                    difference_CI95_low_nm=float(low),difference_CI95_high_nm=float(high)))
    export('additional_paired_intervals_RAW_R152.csv',extra_intervals)
    # Summary is self-contained and explicitly separates today's recalculation from prior acquisition/inference.
    training_log=pd.read_json(ROOT/'runs/formal_8192/updates.jsonl',lines=True)
    assert len(training_log)==8192 and np.array_equal(training_log.step,np.arange(1,8193))
    assert np.isfinite(training_log.select_dtypes('number')).all().all()
    epochs=[]
    for ep,g in training_log.groupby('epoch'):
        dev=read(ROOT/f'runs/formal_8192/dev_{(ep+1)*512:05d}.json')['mean']
        epochs.append(dict(epoch=int(ep)+1,updates=int((ep+1)*512),training_loss_mean=float(g.loss.mean()),
                           dev_task=dev['task'],dev_total=dev['total'],safe_scale=dev['safe_scale'],
                           psf_beta=dev['psf_beta'],weight_entropy=dev['selector_entropy']))
    export('R152_training_epoch_summary.csv',epochs)
    result=dict(recalculation_date='2026-10-02',acquisition_date='2026-09-03',
                primary_metric='Within each scan, sample SD of 30 observed adjacent steps; pool after centering each scan',
                methods=['RAW','R152'],scans=30,frames_per_method=930,circles_per_method=8370,
                observations_adjacent_per_method=900,observations_start_per_method=900,
                measured_boundary_points_per_circle=64,interpolated_radial_directions=720,
                bootstrap={'unit':'whole paired scan','draws':DRAW_COUNT,'seed':SEED},
                integrity=integrity,displacement_parity_max_um=parity,
                within_scan=within,displacement_summary=summary,geometry=geometry,SEM_size=sem_size,SEM_shape=sem_rows,
                endpoints=endpoints,paired_intervals=intervals,additional_paired_intervals=extra_intervals,
                improved_scans_in_primary_metric=int((gains>0).sum()),
                per_scan_improvement_range_percent=[float(gains.min()),float(gains.max())],
                per_scan_improvement_middle90_percent=np.quantile(gains,[.05,.95]).tolist(),
                later24_reduction_percent=float(100*(1-within_map['R152']['later24_pooled_sd_nm']/within_map['RAW']['later24_pooled_sd_nm'])),
                training_epochs=epochs,
                source_paths={'R152_root':str(ROOT),'canonical_prior_record':str(ROOT/'reports/R152_COMPLETE_MODEL_AND_EXPERIMENT_RECORD_20260929.md')})
    (OUT/'complete_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','within_scan':within,'geometry':geometry,'endpoints':endpoints,'paired_intervals':intervals},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
