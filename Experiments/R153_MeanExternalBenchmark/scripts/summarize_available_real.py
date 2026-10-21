"""Full-scan mean displacement, unchanged geometry, paired intervals and fresh runtime."""
from pathlib import Path
import datetime,json,sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from study import MOSR_SOURCE,RECORD,read,save,sha
import numpy as np
import pandas as pd
from scipy.optimize import least_squares
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

METHODS=['RAW','Wiener','EDSR-x1','NAFNet','RDN-x1','RCAN-x1','MOSR']
TH=np.linspace(0,2*np.pi,720,endpoint=False)
OUT=ROOT/'results/available_real';TABLES=ROOT/'reports/data/available_real';FIG=ROOT/'reports/figures/available_real'


def profile(points,center):
    q=points-center;a=np.mod(np.arctan2(q[:,1],q[:,0]),2*np.pi);r=np.linalg.norm(q,axis=1);ix=np.argsort(a);a,r=a[ix],r[ix]
    return np.interp(TH,np.r_[a[-1]-2*np.pi,a,a[0]+2*np.pi],np.r_[r[-1],r,r[0]])


def boot_repeat(a,weights):
    x=a.reshape(30,-1);x=x-x.mean(0);gram=x@x.T/x.shape[1]
    return np.sqrt(np.maximum(weights@np.diag(gram)-np.sum((weights@gram)*weights,axis=1),0)*30/29)


def save_table(name,rows):
    pd.DataFrame(rows).to_csv(TABLES/name,index=False,encoding='utf-8-sig')


def md(frame):
    lines=['| '+' | '.join(frame.columns)+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    for row in frame.itertuples(index=False,name=None):
        lines.append('| '+' | '.join('—' if pd.isna(v) else f'{v:.3f}' if isinstance(v,(float,np.floating)) else str(v) for v in row)+' |')
    return '\n'.join(lines)


def sem_reference():
    cache=OUT/'fixed_SEM_reference.npz'
    sources=[MOSR_SOURCE/'evaluation'/n for n in ['sem_mapping_candidates.json','sem_scale.json','sem_points.npz','sem_current_center9_mapping.csv']]
    hashes={p.name:sha(p) for p in sources}
    if cache.exists():
        assert read(cache.with_suffix('.json'))['source_hashes']==hashes
        with np.load(cache,allow_pickle=False) as z:return {k:z[k] for k in z.files}
    mapping=read(sources[0]);scale=read(sources[1])['scale_nm_per_px'];truth={};diam={}
    with np.load(sources[2],allow_pickle=False) as z:
        for pid in sorted(mapping[0]['sem_ids_by_new_nine']):
            q=z[f'SEM_{pid}'];q=q-q.mean(0)
            def residual(c):
                r=np.linalg.norm(q-c,axis=1);return r-r.mean()
            c=least_squares(residual,[0.,0.],xtol=1e-12,ftol=1e-12,gtol=1e-12).x
            truth[pid]=(q-c)*scale;diam[pid]=2*np.linalg.norm(truth[pid],axis=1).mean()
    references=[]
    for m in mapping:
        refs=[]
        for pid in m['sem_ids_by_new_nine']:
            q=truth[pid].copy()
            if m['candidate']['flip']:q[:,0]*=-1
            for _ in range(m['candidate']['k']):q=np.c_[q[:,1],-q[:,0]]
            refs.append(profile(q,np.zeros(2)))
        references.append(refs)
    current=pd.read_csv(sources[3]).sort_values(['image_row','image_col'])
    assert current.sem_id_working.tolist()==[36,35,34,30,29,28,24,23,22]
    result={'radial_candidates_nm':np.asarray(references),'workbook_diameter_nm':current.sem_diameter_nm.to_numpy(),
            'contour_diameter_nm':np.array([diam[int(i)] for i in current.sem_id_working])}
    np.savez_compressed(cache,**result)
    save(cache.with_suffix('.json'),{'source_hashes':hashes,'optical_LSC_refits':0,
         'SEM_reference_construction':'unchanged original9 SEM circle fits and two fixed orientation candidates; no new direction/scale selection'})
    return result


def arrays_for(method,runs):
    if method in ['RAW','MOSR']:
        key='RAW' if method=='RAW' else 'R152'
        with np.load(RECORD/'data/complete_saved_boundary_points_RAW_R152.npz',allow_pickle=False) as z:
            assert z['run_ids'].tolist()==runs
            return z[key+'_centers_px'],z[key+'_diameters_nm'],z[key+'_points_px'],{'images':930,'attempted_pillars':8370,'failed_pillars':0,'complete_valid_scans':30,'failure_rate':0.,'existing_saved_readouts':True}
    directory=ROOT/'results/readouts'/method;receipt=read(directory/'measurement_complete.json')
    assert receipt['state']=='complete' and receipt['attempted_pillars']==8370
    centers=[];diameters=[];points=[]
    for run in runs:
        meta=read(directory/(run+'.json'))
        assert meta['reader_sha256']==sha(ROOT/'evaluation/measurement_interface.py') and meta['core_sha256']==sha(ROOT/'evaluation/reference_circle_core.py')
        data=pd.read_csv(directory/(run+'.csv')).sort_values(['index','pillar_id'])
        assert len(data)==279 and not data.duplicated(['index','pillar_id']).any()
        assert set(data['index'])==set(range(31)) and set(data.pillar_id)==set(range(1,10))
        centers.append(data[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2))
        diameters.append(2*172.5*data.radius_px.to_numpy().reshape(31,9))
        with np.load(directory/(run+'.npz'),allow_pickle=False) as z:points.append(z['points'])
    return np.stack(centers),np.stack(diameters),np.stack(points),receipt


def main():
    import argparse
    global METHODS,OUT,TABLES,FIG
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');parser.add_argument('--verify-baselines',action='store_true');parser.add_argument('--final',action='store_true');parser.add_argument('--completed-only',action='store_true');args=parser.parse_args()
    assert sum([args.partial,args.verify_baselines,args.final,args.completed_only])<=1
    if args.final:
        METHODS=['RAW','Wiener','EDSR-x1','NAFNet','RDN-x1','RCAN-x1','Restormer','USRNet-x1','SwinIR','MOSR']
        OUT=ROOT/'results/full_benchmark';TABLES=ROOT/'reports/data/full_benchmark';FIG=ROOT/'reports/figures/full_benchmark'
    if args.completed_only:
        scope=read(ROOT/'config/COMPLETED_ONLY_SCOPE.json')
        assert scope['user_explicitly_paused_SwinIR'] and not scope['automatic_training_resume_allowed']
        METHODS=scope['include_methods'];assert len(METHODS)==9 and 'SwinIR' not in METHODS
        OUT=ROOT/'results/completed_models';TABLES=ROOT/'reports/data/completed_models';FIG=ROOT/'reports/figures/completed_models'
    planned=list(METHODS)
    if args.partial:
        METHODS=[m for m in METHODS if m in ['RAW','MOSR'] or (ROOT/'results/readouts'/m/'measurement_complete.json').exists()]
        OUT=ROOT/'results/available_real_partial';TABLES=ROOT/'reports/data/available_real_partial';FIG=ROOT/'reports/figures/available_real_partial'
    if args.verify_baselines:
        METHODS=['RAW','MOSR'];OUT=ROOT/'results/available_baseline_verification';TABLES=OUT/'tables';FIG=OUT/'figures'
    for d in [OUT,TABLES,FIG]:d.mkdir(parents=True,exist_ok=True)
    plan=read(MOSR_SOURCE/'evaluation/capture_plan.json');cal=read(MOSR_SOURCE/'evaluation/calibration.json')
    assert len(plan['frames'])==930 and len(plan['runs'])==30 and cal['nominal_um_per_px']==.1725
    runs=[r['run'] for r in plan['runs']];u=np.array(cal['axis_unit_vector']);v=np.array(cal['transverse_unit_vector'])
    pi=np.array([[f['pi_y_um'] for f in sorted([f for f in plan['frames'] if f['run']==run],key=lambda x:x['index'])] for run in runs])
    draws=np.random.default_rng(20261002).integers(0,30,(20000,30))
    weights=np.zeros((20000,30));np.add.at(weights,(np.repeat(np.arange(20000),30),draws.ravel()),1/30)
    sem=sem_reference();summary=[];per_scan=[];positions=[];displacements=[];pillar_geo=[];sem_rows=[];sem_shape=[];failures=[];boots={};arrays={}
    for method in METHODS:
        centers,diam,points,receipt=arrays_for(method,runs)
        if method not in ['RAW','MOSR']:
            assert read(ROOT/'results/reconstruction'/method/'inference_mode.json')['mode']==read(ROOT/'results/runtime'/(method+'.json'))['mode']
        valid=np.isfinite(centers).all(axis=(1,2,3)) & np.isfinite(diam).all(axis=(1,2)) & np.isfinite(points).all(axis=(1,2,3,4))
        failures.append({'method':method,'images':930,'attempted_pillars':8370,'failed_pillars':receipt['failed_pillars'],
                         'failure_rate':receipt['failure_rate'],'complete_valid_scans':int(valid.sum()),
                         'all30_primary_metrics_available':bool(valid.all())})
        if not valid.all():
            summary.append({'method':method,'state':'incomplete_readout','valid_scans':int(valid.sum())});continue
        radial=np.array([profile(p,c) for p,c in zip(points.reshape(-1,64,2),centers.reshape(-1,2))]).reshape(30,31,9,720)*172.5
        shape=radial-radial.mean(-1,keepdims=True)
        arrays[method]={'diameter':diam,'radial':radial}
        row={'method':method,'state':'complete','valid_scans':30,'mean_diameter_nm':float(diam.mean()),
             'diameter_repeat_sd_nm':float(np.sqrt(diam.var(0,ddof=1).mean())),
             'contour_repeat_sd_nm':float(np.sqrt(radial.var(0,ddof=1).mean())),
             'shape_repeat_sd_nm':float(np.sqrt(shape.var(0,ddof=1).mean())),
             'maximum_diameter_deviation_nm':float(abs(diam-diam.mean(0)).max())}
        bootstrap={metric:boot_repeat(a,weights) for metric,a in [('diameter_repeat_sd_nm',diam),('contour_repeat_sd_nm',radial),('shape_repeat_sd_nm',shape)]}
        for kind,delta,reference in [('adjacent',np.diff(centers,axis=1),np.diff(pi,axis=1)*1000),('start',centers[:,1:]-centers[:,:1],(pi[:,1:]-pi[:,:1])*1000)]:
            vectors=delta.mean(2);d=(vectors@u)*.1725*1000;e=d-reference
            mae=abs(e).mean(1);bias=e.mean(1);mse=(e*e).mean(1)
            row.update({kind+'_mae_nm':float(mae.mean()),kind+'_rmse_nm':float(np.sqrt(mse.mean())),
                        kind+'_bias_nm':float(bias.mean()),kind+'_maximum_abs_error_nm':float(abs(e).max())})
            bootstrap[kind+'_mae_nm']=mae[draws].mean(1)
            bootstrap[kind+'_rmse_nm']=np.sqrt(mse[draws].mean(1));bootstrap[kind+'_bias_nm']=bias[draws].mean(1)
            if kind=='adjacent':
                sd=d.std(1,ddof=1);adj=d
                row.update(pooled_within_scan_sd_nm=float(np.sqrt((sd*sd).mean())),mean_scan_sd_nm=float(sd.mean()),sd_of_scan_sds_nm=float(sd.std(ddof=1)))
                bootstrap['pooled_within_scan_sd_nm']=np.sqrt((sd[draws]**2).mean(1))
            else:
                assert np.max(abs(adj.cumsum(1)-d))<3e-11
                ep=e[:,-1];row.update(endpoint_bias_nm=float(ep.mean()),endpoint_mae_nm=float(abs(ep).mean()),endpoint_rmse_nm=float(np.sqrt((ep*ep).mean())),endpoint_error_sd_nm=float(ep.std(ddof=1)))
                bootstrap['endpoint_bias_nm']=ep[draws].mean(1);bootstrap['endpoint_mae_nm']=abs(ep[draws]).mean(1)
            for i,run in enumerate(runs):
                per_scan.append({'method':method,'run':run,'scan':i+1,'kind':kind,'mae_nm':float(mae[i]),'bias_nm':float(bias[i]),
                                 'within_scan_sd_nm':float(sd[i]) if kind=='adjacent' else None,'endpoint_error_nm':float(e[i,-1]) if kind=='start' else None})
                for j in range(30):displacements.append({'method':method,'run':run,'scan':i+1,'kind':kind,'step':j+1,'displacement_nm':d[i,j],'PI_displacement_nm':reference[i,j],'error_nm':e[i,j],
                                                        'dx_px':vectors[i,j,0],'dy_px':vectors[i,j,1],'transverse_nm':float(vectors[i,j]@v)*172.5})
            for j in range(30):positions.append({'method':method,'kind':kind,'step':j+1,'mean_displacement_nm':float(d[:,j].mean()),'displacement_sd_nm':float(d[:,j].std(ddof=1)),
                                                'mean_error_nm':float(e[:,j].mean()),'error_sd_nm':float(e[:,j].std(ddof=1))})
        observed=diam.mean((0,1))
        for ref_name,ref in [('SEM_workbook',sem['workbook_diameter_nm']),('SEM_contour',sem['contour_diameter_nm'])]:
            diff=observed-ref;metric=ref_name+'_diameter_MAE_nm';row[metric]=float(abs(diff).mean())
            bootstrap[metric]=abs(np.einsum('br,rk->bk',weights,diam.mean(1))-ref).mean(1)
            for k in range(9):sem_rows.append({'method':method,'reference':ref_name,'pillar':k+1,'reference_diameter_nm':ref[k],'observed_diameter_nm':observed[k],'signed_difference_nm':diff[k]})
        for index,ref in enumerate(sem['radial_candidates_nm'],1):
            error=abs(radial-ref);sherror=abs(shape-(ref-ref.mean(-1,keepdims=True)))
            sem_shape.append({'method':method,'mapping_candidate':index,'full_radial_difference_nm':float(error.mean()),'de_size_shape_difference_nm':float(sherror.mean())})
            for name,a in [('full_radial_difference_nm',error),('de_size_shape_difference_nm',sherror)]:
                metric=f'SEM_candidate{index}_{name}';row[metric]=float(a.mean());bootstrap[metric]=weights@a.mean((1,2,3))
        for k in range(9):pillar_geo.append({'method':method,'pillar':k+1,'mean_diameter_nm':float(diam[:,:,k].mean()),
           'diameter_repeat_sd_nm':float(np.sqrt(diam[:,:,k].var(0,ddof=1).mean())),
           'contour_repeat_sd_nm':float(np.sqrt(radial[:,:,k].var(0,ddof=1).mean())),
           'shape_repeat_sd_nm':float(np.sqrt(shape[:,:,k].var(0,ddof=1).mean()))})
        np.savez_compressed(OUT/(method+'_measurements.npz'),centers_px=centers,diameters_nm=diam,points_px=points,radial_nm=radial,run_ids=np.array(runs))
        boots[method]=bootstrap;summary.append(row);print('ANALYZED',method,flush=True)
    # Verify reused baselines against the previous complete geometry and new mean record.
    baseline=pd.read_csv(RECORD/'data/geometry_summary_RAW_R152.csv');mean=pd.read_csv(ROOT/'reports/data/aggregation_summary.csv')
    for row in summary:
        if row['method'] not in ['RAW','MOSR']:continue
        key='RAW' if row['method']=='RAW' else 'R152';old=baseline[baseline.method==key].iloc[0]
        for metric in ['mean_diameter_nm','diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm']:assert abs(row[metric]-old[metric])<1e-7
        old=mean[(mean.method==row['method'])&(mean.aggregation=='mean')&(mean.kind=='adjacent')].iloc[0]
        assert abs(row['pooled_within_scan_sd_nm']-old.pooled_within_scan_sd_nm)<1e-8
        assert abs(row['adjacent_mae_nm']-old.mae_nm)<1e-8
    pair=[];lookup={r['method']:r for r in summary}
    for method in METHODS:
        if method=='MOSR' or method not in boots:continue
        for metric in boots['MOSR']:
            samples=boots['MOSR'][metric]-boots[method][metric];low,high=np.quantile(samples,[.025,.975])
            pair.append({'reference_method':method,'comparison':'MOSR minus '+method,'metric':metric,
                         'reference':lookup[method][metric],'MOSR':lookup['MOSR'][metric],
                         'difference':lookup['MOSR'][metric]-lookup[method][metric],'CI95_low':float(low),'CI95_high':float(high)})
    previous=pd.read_csv(RECORD/'data/whole_scan_paired_intervals_RAW_R152.csv')
    for metric in ['diameter_repeat_sd_nm','contour_repeat_sd_nm','shape_repeat_sd_nm']:
        current=next(x for x in pair if x['reference_method']=='RAW' and x['metric']==metric)
        original=previous[previous.metric==metric].iloc[0]
        assert abs(current['CI95_low']-original.difference_CI95_low_nm)<1e-7
        assert abs(current['CI95_high']-original.difference_CI95_high_nm)<1e-7
    if args.verify_baselines:
        save(OUT/'verified.json',{'state':'passed','geometry_parity':True,'mean_displacement_parity':True,'geometry_paired_CI_parity':True,
             'optical_LSC_refits':0,'full_MOSR_reconstructions':0,'summary':summary})
        print('SAVED BASELINE STATISTICS AND PAIRED GEOMETRY PARITY VERIFIED',flush=True);return
    runtime=[];timing_detail=[]
    for method in planned:
        data=read(ROOT/'results/runtime'/(method+'.json'));assert data['state']=='complete' and data['batch']==1 and data['precision']=='FP32' and data['TF32'] is False
        samples=[s for f in data['frames'] for s in f['samples']];assert len(samples)==15
        values=np.array([s['forward_seconds'] for s in samples]);counts=0 if method in ['RAW','Wiener'] else 1207105 if method=='MOSR' else read(ROOT/'runs'/method/'training_complete.json')['total_parameters']
        runtime.append({'method':method,'parameters':counts,'mean_seconds':float(values.mean()),'median_seconds':float(np.median(values)),'sd_seconds':float(values.std(ddof=1)),
                        'minimum_seconds':float(values.min()),'maximum_seconds':float(values.max()),
                        'peak_allocated_GiB':max(s['peak_allocated_bytes'] for s in samples)/2**30,'peak_reserved_GiB':max(s['peak_reserved_bytes'] for s in samples)/2**30,
                        'mode':data['mode'],'gpu':data['gpu'],'precision':'FP32','images':3,'repetitions_per_image':5})
        for f in data['frames']:
            for s in f['samples']:timing_detail.append({'method':method,'run':f['run'],'index':f['index'],**s})
    for name,rows in [('summary.csv',summary),('per_scan.csv',per_scan),('per_position.csv',positions),('all_displacements.csv',displacements),
                      ('per_pillar_geometry.csv',pillar_geo),('SEM_size_by_pillar.csv',sem_rows),('SEM_shape.csv',sem_shape),('paired_intervals.csv',pair),
                      ('runtime_summary.csv',runtime),('runtime_samples.csv',timing_detail),('failures.csv',failures)]:save_table(name,rows)
    plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
    frame=pd.DataFrame(summary);complete=frame[frame.state=='complete'].set_index('method')
    fig,axs=plt.subplots(1,3,figsize=(10,3.5))
    for ax,metric,label in zip(axs,['pooled_within_scan_sd_nm','adjacent_mae_nm','contour_repeat_sd_nm'],['Within-scan step SD (nm)','Adjacent PI MAE (nm)','Contour repeatability SD (nm)']):
        ax.bar(np.arange(len(complete)),complete[metric],color=['0.15' if m=='MOSR' else '0.75' for m in complete.index],edgecolor='0.15',linewidth=.7)
        ax.set_xticks(np.arange(len(complete)),complete.index,rotation=55,ha='right');ax.set_ylabel(label);ax.grid(axis='y',color='0.9',linewidth=.5);ax.set_axisbelow(True)
    fig.tight_layout()
    for ext in ['png','svg','pdf']:fig.savefig(FIG/('primary_results.'+ext),dpi=300,bbox_inches='tight')
    plt.close(fig)
    main_table=frame[['method','valid_scans','pooled_within_scan_sd_nm','adjacent_mae_nm','contour_repeat_sd_nm']].rename(columns={'method':'方法','valid_scans':'完整掃描','pooled_within_scan_sd_nm':'單趟波動合併SD nm','adjacent_mae_nm':'相鄰PI MAE nm','contour_repeat_sd_nm':'輪廓重複SD nm'})
    speed=pd.DataFrame(runtime).rename(columns={'method':'方法','mean_seconds':'平均重建秒數','peak_allocated_GiB':'GPU配置峰值 GiB','peak_reserved_GiB':'GPU保留峰值 GiB','mode':'推論方式'})
    speed.loc[speed['方法']=='RAW','平均重建秒數']=np.nan
    geometry=frame[['method','diameter_repeat_sd_nm','shape_repeat_sd_nm','SEM_workbook_diameter_MAE_nm','start_mae_nm','endpoint_bias_nm']].rename(columns={'method':'方法','diameter_repeat_sd_nm':'直徑SD nm','shape_repeat_sd_nm':'去尺寸形狀SD nm','SEM_workbook_diameter_MAE_nm':'SEM工作表直徑差 nm','start_mae_nm':'起點相對PI MAE nm','endpoint_bias_nm':'終點有號PI差 nm'})
    primary_metrics={'pooled_within_scan_sd_nm':'單趟波動合併SD','adjacent_mae_nm':'相鄰PI MAE','contour_repeat_sd_nm':'輪廓重複SD'}
    interpretation=[]
    for r in pair:
        if r['metric'] not in primary_metrics:continue
        conclusion='本批MOSR較低' if r['CI95_high']<0 else '本批比較方法較低' if r['CI95_low']>0 else '區間跨零，差異尚未確定'
        interpretation.append({'比較方法':r['reference_method'],'指標':primary_metrics[r['metric']],
                               'MOSR減比較方法 nm':r['difference'],'95%下界 nm':r['CI95_low'],'95%上界 nm':r['CI95_high'],'判讀':conclusion})
    winners=[]
    for metric,label in primary_metrics.items():
        name=complete[metric].idxmin();value=complete.loc[name,metric]
        winners.append(f'{label}之本批最低點估計為{name}（{value:.3f} nm）')
    sem_table=pd.DataFrame(sem_shape).rename(columns={'method':'方法','mapping_candidate':'固定方向候選','full_radial_difference_nm':'完整徑向SEM平均絕對差 nm','de_size_shape_difference_nm':'去尺寸形狀SEM平均絕對差 nm'})
    scan_comparison=[]
    scans=pd.DataFrame(per_scan)
    mosr_s=scans[(scans.method=='MOSR')&(scans.kind=='adjacent')].sort_values('scan').within_scan_sd_nm.to_numpy()
    for method in METHODS:
        if method=='MOSR' or method not in boots:continue
        own=scans[(scans.method==method)&(scans.kind=='adjacent')].sort_values('scan').within_scan_sd_nm.to_numpy()
        gain=100*(1-mosr_s/own)
        scan_comparison.append({'比較方法':method,'MOSR波動較低趟數':int((mosr_s<own).sum()),'總趟數':30,
                                '逐趟降低率最小%':float(gain.min()),'逐趟降低率最大%':float(gain.max())})
    save_table('scan_improvement_comparison.csv',scan_comparison)
    epochs='；'.join(f"{m}訓練{read(ROOT/'runs'/m/'training_complete.json')['epochs_trained']}輪、選第{read(ROOT/'runs'/m/'training_complete.json')['selected_epoch']}輪" for m in METHODS if m not in ['RAW','Wiener','MOSR'])
    text='''# 已完成模型之完整實拍驗證與效率比較

本階段包括RAW、Wiener、EDSR-x1、NAFNet、RDN-x1、RCAN-x1與MOSR。所有外部方法完成相同930張實拍影像、30次掃描×31位置×固定九顆的量測。RAW/MOSR使用既有保存圓心與輪廓，未重新擬合或重跑930張MOSR重建；效率測試另用三張固定影像作少量新前向量測。

'''+epochs+'''。實際輪數不同，屬使用者指定的較短訓練比較，不能宣稱相同訓練時間或各模型已充分收斂。全部模型與Wiener設定僅依合成資料訓練／選擇，實拍、PI與SEM沒有用於挑設定或权重。

## 主要實拍結果

'''+md(main_table)+'''

位移先取九顆二維位移向量之算術平均，再投影至原固定方向；每趟以30步样本SD表示單趟波動，30趟以方差平均開根號合併。PI MAE使用同影格對Y回授差。輪廓使用固定720方向，先逐位置／物件／方向跨30趟求SD再合併。全部資料保留，無後置銳化、尺寸修正、重新配準、逐圖對比調整或剔除不利點。

![主要結果灰階比較](figures/available_real/primary_results.png)

## 尺寸與長距離

'''+md(geometry)+'''

重複性與SEM尺寸差分開解讀；相對起點或終點是否改善，須看完整掃描配對區間，不由短步波動直接外推。

## 新效率測試

'''+md(speed[['方法','平均重建秒數','GPU配置峰值 GiB','GPU保留峰值 GiB','推論方式']])+'''

相同RTX A6000、FP32、batch=1、TF32關閉，固定三張1544×2064影像，各暖身兩次並量測五次。時間只含已同步完成的前向，讀檔、輸入傳輸、輸出檢查與CPU量測不計入。配置／保留峰值包括該程序模型、光學模組、輸入輸出與暫存。RAW為原圖，不需重建，其identity前向成本不作重建效能優勢；原始樣本完整保留。

native_full_frame表示原生整張。native_MOSR_stage_tiles為MOSR原有FFT／背景完整處理及512核心、24邊緣的階段分塊。memory_fallback_tiles僅在原生整張CUDA記憶體不足時啟用，固定512核心與192邊緣，只取核心、不重疊平均。具有全域注意力或全域池化的模型使用此方式會改變上下文，不能當作已證明整張等價；每個模型保持同一方式跑全部影像，另保留原生整張不足的紀錄。

## 全掃描配對比較與完整資料

data/available_real/paired_intervals.csv保存MOSR減各方法的所有指標差值與95%區間，20000次、種子20261002，整趟配對重抽樣。對非負波動或MAE，負差值代表MOSR較低；有號偏差須另看距零大小。多個比較未作家族錯誤校正，不從中挑最有利結果宣稱全指標最佳。

summary.csv、per_scan.csv、per_position.csv、all_displacements.csv、per_pillar_geometry.csv及兩種SEM參照／兩個固定方向候選均完整保留。failures.csv記錄覆蓋與失敗，缺任何完整量測的方法不給全30趟主要指標，不能默默只分析成功子集。runtime_samples.csv有每張、每次時間與峰值。SEM方向与尺度維持原定義；重複抽樣區間不含完整PI、尺度或SEM誤差預算。此為本批資料的比較，不是跨樣品普遍結論。
'''
    for a,b in [('权重','權重'),('样本','樣本'),('方向与','方向與')]:text=text.replace(a,b)
    details='''
## 三項目標分開判斷

'''+ '；'.join(winners)+'''。這是本批資料的點估計排名，不等於已證明跨樣品的普遍優劣；請同時閱讀以下配對區間，不以一個總分混合三項目標。

'''+md(pd.DataFrame(interpretation))+'''

負差值表示MOSR數值較低；非零區間是本批完整掃描配對估計，不是已校正多重比較的結論。區間跨零時不能以點估計較小宣稱確定改善。

### 30趟改善範圍

'''+md(pd.DataFrame(scan_comparison))+'''

此處逐趟降低範圍是本批觀察範圍，負降低率表示MOSR該趟波動更大，不是改善。它與合併SD降低率或合併降低率95%區間不同。

### SEM輪廓參照

'''+md(sem_table)+'''

兩個方向候選皆沿用原定義，沒有依新模型結果挑較有利方向。完整徑向差保留尺寸影響；去尺寸形狀差先各自扣去平均半徑。輪廓重複SD描述30次重拍穩定性，這裡的SEM差才是幾何參照，兩者不可互換。使用實際SEM校正的系統PSF條件下，這些結果仍是相同校正條件的參照比較，不宣稱完整獨立絕對真值。
'''
    text += details
    text+='''
## 可供論文使用的計算與訓練細節

固定尺度172.5 nm/pixel，固定方向u=(−0.9998766245119538,0.015707824629190823)。對每趟r、位置j及柱體k，以保存／固定讀法所得圓心c計算Δc_k=c(r,j,k)−c(r,a,k)，其中相鄰步a=j−1，相對起點a=0。d=172.5 uᵀ[(1/9)Σ_kΔc_k]，e=d−1000[PI_Y(r,j)−PI_Y(r,a)]。每趟30步樣本SD分母29，30趟合併SD為sqrt[(1/30)Σ_rs_r²]。PI MAE使用全部900個相鄰誤差的絕對值平均；相對起點另用各位置對起點的直接圓心差計算。

直徑重複SD=sqrt{mean_(位置,物件)[Var_掃描(D)]}，每個樣本變異數分母29。輪廓先用該輪廓的LSC圓心平移對齊，64邊界點作週期插值至720固定方向，q為該方向半徑；完整輪廓SD=sqrt{mean_(位置,物件,方向)[Var_掃描(q)]}。去尺寸形狀先每個輪廓各自扣平均半徑再同樣合併。沒有依形狀重新旋轉、縮放或配準。SEM工作表直徑差=mean_k|mean_(r,j)D(r,j,k)−D_SEM(k)|，不是將8370個光學直徑各自對SEM作獨立觀測平均。

各方法使用完全相同物件對應與原固定讀法：RAW保存追蹤種子、29×29局部區域、ACM13次、沿法線±2.4 pixel搜尋最大灰階梯度、64個亞像素邊界點與LSC。固定讀法內原有的局部ACM正規化與梯度平滑照用，沒有在模型原生影像輸出後新增影像修正。既有RAW/MOSR圓心與邊界直接讀取，不重新擬合。

外部模型資料為同一TIFF合成銀行，場景分組512訓練／128驗證／128測試，每場景4視圖。每輪2048組影像，batch4、512次更新；384×384輸入，共同96×96有效監督區域。模型用各自常用目標從零訓練：EDSR-x1／RDN-x1／RCAN-x1使用L1與Adam，初始學習率1e−4；NAFNet使用作者PSNR目標與AdamW，初始1e−3。合成驗證每輪一次，僅依驗證分數保留權重；實拍與SEM結果不參與挑設定。使用者改為較短訓練後，完整保留各模型實際輪數差異，不能宣稱相同更新預算或充分收斂。

此為固定資料與量測規則下的整體方法比較，原生架構、訓練目標與實際輪數仍有差異；因此不能由本表單獨歸因某一PSF模組、共享主幹或損失項的因果效果，也不將各方法不同的PSF先驗資訊混寫成完全相同輸入條件。

EDSR-x1為作者基準16殘差塊、64通道，灰階與x1適配；RDN-x1為作者明示之配置A（20個密集區塊、每塊6層、成長32、主幹64）；RCAN-x1為10組、每組20殘差塊、64通道、通道注意力縮減16；NAFNet採作者GoPro寬32與TLC設定，編碼區塊[1,1,1,28]、中間1、解碼[1,1,1,1]。全部保留作者數值程式與固定適配；精確來源版本、普通訓練設定及原先時間上限修正隨交接包附上。MOSR沿用原已驗證的混合結構、光學模組、抗混疊與原生分塊，未為比較重新設計或訓練。
'''
    text+='\n## 量測覆蓋與失敗\n\n'+md(pd.DataFrame(failures).rename(columns={'method':'方法','images':'影像數','attempted_pillars':'嘗試量測數','failed_pillars':'失敗量測數','failure_rate':'失敗率','complete_valid_scans':'完整有效趟數','all30_primary_metrics_available':'全30趟主指標可用'}))+'\n\n程序未拋出量測錯誤不等於已證明輪廓正確；因此重複性、SEM幾何參照及實際輪廓示例仍分開呈現。\n'
    if args.partial:
        text=text.replace('所有外部方法完成相同930張實拍影像、30次掃描×31位置×固定九顆的量測。',
            '外部方法完整實拍驗證仍在執行；主要實拍表目前只列已完成930張量測的方法：'+ '、'.join(METHODS)+'。其他方法不填推估數值；效率表列已完成相同三張影像新測試的七種方法。')
        text=text.replace('figures/available_real/primary_results.png','figures/available_real_partial/primary_results.png').replace('data/available_real/paired_intervals.csv','data/available_real_partial/paired_intervals.csv')
    assert not __import__('re').search(r'\bR(?:140|148|150|152|153)\b',text)
    if args.final or args.completed_only:
        text=text.replace('本階段包括RAW、Wiener、EDSR-x1、NAFNet、RDN-x1、RCAN-x1與MOSR。','本比較包括'+ '、'.join(METHODS)+'。')
        text=text.replace('figures/available_real/primary_results.png','figures/full_benchmark/primary_results.png').replace('data/available_real/paired_intervals.csv','data/full_benchmark/paired_intervals.csv')
        text+='\n## 後續三方法的固定條件\n\nRestormer採作者灰階dim48、區塊[4,6,6,8]、精煉4、heads[1,2,4,8]、BiasFree，L1／AdamW初始3e−4。USRNet-x1採作者8次展開、prior[64,128,256,512]、nb2，L1／Adam初始1e−4及作者orthogonal gain0.2；訓練提供合成已知PSF與真實合成噪聲，驗證／測試／實拍固定平均PSF與1.5灰階噪聲，不依實拍調整。SwinIR採作者灰階去噪頭、embed180、6×6depth、heads6×6、window8、MLP2，作者Charbonnier／Adam初始2e−4、EMA0.999。三者皆使用原指定8輪上限及同一資料／有效區域／合成驗證。原七方法930張與效率資料直接重用，未重建、重新量測或重測。\n'
        blocked=read(ROOT/'config/blocked_models.json')
        text+='\n## 官方後端阻礙（不冒充完成）\n\n'+'\n\n'.join(m+'：'+item['reason'] for m,item in blocked.items())+'\n\n本文件完成的是可執行十方法的比較與上述兩方法阻礙紀錄；不把blocked方法算作已訓練／已驗證，也不以替代簡化網路填數值。\n'
    if args.completed_only:
        text=text.replace('figures/full_benchmark/','figures/completed_models/').replace('data/full_benchmark/','data/completed_models/').replace('可執行十方法','九種已完成驗證的方法').replace('三者皆使用原指定8輪上限','上述已完成模型使用原指定8輪上限')
        text=text.replace('後續三方法的固定條件','新增兩方法的固定條件').replace('原七方法930張與效率資料直接重用，未重建、重新量測或重測。','原七方法930張與效率資料直接重用，未重建、重新量測或重測；本次只新增Restormer與USRNet-x1，SwinIR未完成且暫停。')
        text+='\n## 使用者指定的論文交付範圍\n\n本次完整比較六個已訓練外部模型，加上RAW、Wiener與MOSR，共九方法。SwinIR依使用者要求暫停，保存點保留，未完成訓練且未驗證，不列入結果或排名，也不自動續訓。SwinIR架構／原規則僅作原计划紀錄，不當作本次已完成比較。U-Net、MambaIRv2仍有上述官方後端阻礙。原先七方法實拍與效率結果直接重用，只新增Restormer及USRNet-x1。\n'
        text=text.replace('原计划','原計畫')
    if args.final and (ROOT/'config/USER_RESUME_20261006.json').exists():
        text=text.replace('原七方法930張與效率資料直接重用，未重建、重新量測或重測。','原九方法930張、8370讀值及135次效率資料直接重用，未重建、重新量測或重測；本次只新增SwinIR的完整930張、8370讀值與15次效率。')
        text+='\n## 較短訓練的完整記錄\n\nRDN-x1完成14個完整輪次，另保存第15輪的128次未完成輪更新；選用的是第14輪合成驗證權重，不將未完成輪當作已驗證輪次。EDSR-x1／NAFNet的32輪與後續四模型的8輪如實分列。這項時間限制屬本次比較條件，不能推定各架構均已達最佳訓練結果。\n'
    (ROOT/'reports'/('COMPLETED_MODELS_RESULTS.md' if args.completed_only else 'FINAL_BENCHMARK_RESULTS.md' if args.final else 'AVAILABLE_MODELS_PROGRESS.md' if args.partial else 'AVAILABLE_MODELS_REAL_RESULTS.md')).write_text(text,encoding='utf-8')
    save(OUT/'complete.json',{'state':'partial' if args.partial else 'complete','methods':METHODS,'planned_methods':planned,'full_real_frames_per_method':930,'measurement_attempts_per_method':8370,
         'all30_scans_retained':True,'paired_intervals':len(pair),'bootstrap_draws':20000,'bootstrap_seed':20261002,
         'saved_RAW_MOSR_baseline_parity':True,'all_methods_complete_valid_scans':{x['method']:x['complete_valid_scans'] for x in failures},
         'new_RAW_MOSR_LSC_fits':0,'new_MOSR_full930_inference':False,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
         'full_external_training_queue_complete':bool(args.final),'full_benchmark_complete':bool(args.final),
         'blocked_official_backends':list(read(ROOT/'config/blocked_models.json')) if args.final or args.completed_only else [],
         'completed_models_user_scope_complete':bool(args.completed_only),'paused_methods':['SwinIR'] if args.completed_only else []})
    print('AVAILABLE REAL COMPARISON COMPLETE',flush=True)
    if not args.partial and not args.final and not args.completed_only:
        efficiency_path=ROOT/'reports/AVAILABLE_MODELS_EFFICIENCY.md'
        content=efficiency_path.read_text(encoding='utf-8').replace('外部模型的完整實拍位移、輪廓與SEM比較仍在執行，不以本表推定重建效果或量測排名。','本階段七方法的完整實拍比較已完成；效率與量測指標分開解讀，後續未完成模型不在本階段排名。')
        efficiency_path.write_text(content,encoding='utf-8')
        efficiency_receipt=read(ROOT/'results/runtime/available_efficiency_verified.json')
        efficiency_receipt['full_real_metrology_complete']=True;efficiency_receipt['completed_real_scope']=METHODS
        save(ROOT/'results/runtime/available_efficiency_verified.json',efficiency_receipt)
        from scripts.build_available_handoff import build
        build(partial=False)
    if args.final:
        from scripts.build_available_handoff import build
        build(partial=False,final=True)
    if args.completed_only:
        from scripts.build_available_handoff import build
        build(partial=False,completed_only=True)


if __name__=='__main__':main()
