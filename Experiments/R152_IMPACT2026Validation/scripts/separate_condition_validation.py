"""Recheck thesis 20x and original 50x separately, with the thesis LSC family."""
from pathlib import Path
import os,sys,json,time,hashlib,argparse
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from PIL import Image
from scipy.io import loadmat

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
SRC=Path('D:/GMM_2_Final/Experiments/R152_R148v2_SafeAdaptivePSF')
OUT=ROOT/'results/separate_conditions'
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
from lsc_fixed_state import measure_inflection_lsc_fixed

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def measure(image,seeds,ids,cfg):
    rows=[]
    for pid,(x,y) in zip(ids,seeds):
        patch,pc,origin=backend.crop_around(image,(float(x),float(y)),cfg['patch_half'])
        result=measure_inflection_lsc_fixed(patch,pc,cfg['radius_px'],sample_count=cfg['sample_count'],acm_iterations=cfg['acm_iterations'],normal_half_width_px=cfg['normal_half_width_px'],polarity='dark')
        c=result.lsc
        rows.append(dict(pillar_id=int(pid),center_x_px=c.cx+origin[0],center_y_px=c.cy+origin[1],radius_px=c.radius))
    return rows
def roi(raw,seeds,pitch):
    margin=int(np.ceil(.55*pitch))
    x0=max(0,int(np.floor(seeds[:,0].min()))-margin);x1=min(raw.shape[1],int(np.ceil(seeds[:,0].max()))+margin+1)
    y0=max(0,int(np.floor(seeds[:,1].min()))-margin);y1=min(raw.shape[0],int(np.ceil(seeds[:,1].max()))+margin+1)
    return raw[y0:y1,x0:x1],np.array([x0,y0])

def thesis_run(run):
    import cv2
    cv2.setNumThreads(1)
    dest=OUT/'20x_thesis';dest.mkdir(parents=True,exist_ok=True)
    plan=load(SRC/'evaluation/capture_plan.json');cfg=load(SRC/'evaluation/measurement_config.json')
    tracking=pd.read_csv(SRC/'evaluation/tracking.csv');tracking=tracking[tracking.run==run]
    psf=loadmat(backend.SWEEP_ROOT/'20x_deconvolution_sweep.mat')['psf']
    frames=[f for f in plan['frames'] if f['run']==run]
    orig={m:pd.read_csv(SRC/(f'evaluation/baseline_centers/Raw/{run}.csv' if m=='Raw' else f'results/centers/{run}.csv')).set_index(['index','pillar_id']).sort_index() for m in ['Raw','MOSR']}
    rows=[];evidence=[];maxerr=0;start=time.perf_counter()
    for f in frames:
        fi=f['index'];source=Path(f['source']['path']);assert sha(source)==f['source']['sha256']
        path=SRC/f'results/reconstruction/{run}/{fi+1:02d}.npz';receipt=load(path.with_suffix('.json'))
        assert sha(path)==receipt['output_sha256'] and receipt['source']['sha256']==f['source']['sha256']
        assert receipt['checkpoint_sha256']==load(OUT/'protocol_lock.json')['checkpoint_sha256']
        raw=backend.load_grayscale(source);recon=np.load(path)['output'].astype(np.float64)
        seeds=tracking[tracking['index']==fi].sort_values('pillar_id')[['seed_x_px','seed_y_px']].to_numpy();ids=list(range(1,10));assert seeds.shape==(9,2)
        region,offset=roi(raw,seeds,cfg['pitch_px'])
        images={'Raw':(raw,np.array([0,0])),'Wiener':(backend.wiener_contrast_restore(region,psf,backend.NSR,pitch_px=cfg['pitch_px']),offset),'MOSR':(recon,np.array([0,0]))}
        for m,(image,origin) in images.items():
            found=measure(image,seeds-origin,ids,cfg)
            for r in found:
                r['center_x_px']+=origin[0];r['center_y_px']+=origin[1]
                if m in orig:
                    old=orig[m].loc[(fi,r['pillar_id'])]
                    err=float(np.max(abs(old[['center_x_px','center_y_px','radius_px']].to_numpy(dtype=float)-np.array([r[k] for k in ['center_x_px','center_y_px','radius_px']]))))
                    maxerr=max(maxerr,err);assert err<1e-7,(run,fi,m,err)
                rows.append(dict(run=run,run_index=f['run_index'],index=fi,method=m,**r))
        evidence.append(dict(run=run,index=fi,raw_path=str(source),raw_sha256=f['source']['sha256'],mosr_path=str(path),mosr_sha256=receipt['output_sha256']))
    df=pd.DataFrame(rows);assert len(df)==837
    df.to_csv(dest/f'{run}_centers.csv',index=False)
    save(dest/f'{run}_audit.json',dict(passed=True,frames=31,circle_rows=len(df),max_source_center_difference_px=maxerr,elapsed_seconds=time.perf_counter()-start,source_records=evidence))
    return dict(run=run,max_source_center_difference_px=maxerr,elapsed_seconds=time.perf_counter()-start)

def run20():
    plan=load(SRC/'evaluation/capture_plan.json');runs=[r['run'] for r in plan['runs']]
    status=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        for result in pool.map(thesis_run,runs):
            status.append(result);save(OUT/'20x_status.json',dict(state='running',completed_scans=len(status),total_scans=30));print('20X_REMEASURE',len(status),'/30',result['run'],flush=True)
    centers=pd.concat([pd.read_csv(OUT/f'20x_thesis/{run}_centers.csv') for run in runs],ignore_index=True)
    centers.to_csv(OUT/'20x_all_centers.csv',index=False)
    axis=np.array(load(SRC/'evaluation/calibration.json')['axis_unit_vector']);steps=[]
    for (run,m),g in centers.groupby(['run','method']):
        coords=g.sort_values(['index','pillar_id'])[['center_x_px','center_y_px']].to_numpy().reshape(31,9,2)
        d=np.median(np.diff(coords,axis=0),axis=1)@axis*172.5
        for j,value in enumerate(d,1):steps.append(dict(run=run,run_index=int(g.run_index.iloc[0]),method=m,step=j,displacement_nm=value))
    steps=pd.DataFrame(steps);assert len(steps)==2700
    stats=steps.groupby(['run','run_index','method']).displacement_nm.agg(n='count',mean_nm='mean',step_sd_nm='std').reset_index();assert stats.n.eq(30).all()
    steps.to_csv(OUT/'20x_steps.csv',index=False);stats.to_csv(OUT/'20x_scan_sd.csv',index=False)
    source_summary=load(Path('D:/GMM_2_Final/Thesis_MOSR_Evidence/Model_Comparison_Reports/WithinScan_30Step_16Models_20260930/summary.json'))
    summary={};wide=stats.pivot(index='run_index',columns='method',values='step_sd_nm')
    for m in ['Raw','Wiener','MOSR']:
        v=wide[m].to_numpy();gain=100*(1-v/wide.Raw.to_numpy())
        summary[m]=dict(mean_scan_sd_nm=float(v.mean()),pooled_within_scan_sd_nm=float(np.sqrt(np.mean(v*v))),min_scan_sd_nm=float(v.min()),max_scan_sd_nm=float(v.max()),improved_scans_vs_raw=int((v<wide.Raw.to_numpy()).sum()),per_scan_gain_min_pct=float(gain.min()),per_scan_gain_max_pct=float(gain.max()))
        if m!='Wiener':
            ref=next(r for r in source_summary['ranked_summary'] if r['display']==('RAW' if m=='Raw' else 'R152'))
            assert abs(summary[m]['pooled_within_scan_sd_nm']-ref['pooled_within_scan_sd_nm'])<1e-8
    save(OUT/'20x_complete.json',dict(passed=True,frames=930,scans=30,steps_per_scan=30,methods=summary,max_source_center_difference_px=max(r['max_source_center_difference_px'] for r in status),excluded_frames=0,excluded_steps=0,reader='thesis normal-gradient geometric LSC with per-pillar state reset'))
    save(OUT/'20x_status.json',dict(state='complete',completed_scans=30,total_scans=30,report='20x_complete.json'))
    print(json.dumps(summary,indent=2),flush=True)

def run50():
    import torch
    sys.path.insert(0,str(SRC))
    from model import Model
    from utils import setup
    from objective_optics import install_50x,configure_optical_input,load_original_kernel
    setup(1309001);torch.set_num_threads(2)
    cfg=load(SRC/'config/model.json');rec=load(SRC/'runs/formal_8192/training_complete.json')['deployed_checkpoint'];assert sha(rec['path'])==rec['sha256']
    model=Model(cfg,SRC).cuda().eval();model.load_state_dict(torch.load(rec['path'],map_location='cpu',weights_only=False)['model'],strict=True)
    params={k:v.detach().cpu().clone() for k,v in model.named_parameters()};installed=install_50x(model,cfg,SRC)
    k=load_original_kernel();assert np.array_equal(model.base.optics.mean_kernel.cpu().numpy()[0,0],k.astype('float32'))
    assert np.array_equal(model.psf_fusion.bank.cpu().numpy()[0,0],k.astype('float32'))
    conf=load(ROOT/'sources/sequence_config.json');pairs=pd.read_csv(ROOT/'sources/original_locked_pairs.csv')
    baseline=pd.read_csv(ROOT/'results/definition_audit/state_centers.csv');baseline=baseline[(baseline.phase==0)&baseline.method.isin(['Raw','Wiener','R152'])].set_index(['sequence','method','frame_index','pillar_id']).sort_index()
    backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv'
    records=[];rows=[];t0=time.perf_counter();full_tiled=None;max_center_err=0
    for seq in ['50x_x_0p5um','50x_x_1um']:
        s=conf['sequences'][seq];chosen=pairs[pairs.sequence==seq];frames=sorted(set(chosen.start_frame_index)|set(chosen.end_frame_index))
        mc=dict(patch_half=34,radius_px=s['radius_px'],sample_count=96,acm_iterations=15,normal_half_width_px=4.0)
        for fi in frames:
            old=ROOT/f'results/50x_calibrated/reconstruction/{seq}/frame_{fi:04d}.npz';receipt=load(old.with_suffix('.json'))
            source=Path(s['raw_dir'])/f'frame_{fi:04d}.bmp'
            assert sha(source)==receipt['source_sha256'] and sha(old)==receipt['output_sha256'] and receipt['checkpoint_sha256']==rec['sha256'] and receipt['bank_sha256']==installed['effective_bank_sha256']
            raw=backend.load_grayscale(source);x=torch.from_numpy(raw.astype(np.float32)[None,None]).cuda()
            with torch.inference_mode():new=model.forward_tiled(x)
            recon=new.cpu().numpy()[0,0];saved=np.load(old)['output'];replay=float(abs(recon-saved).max());assert replay<1e-7,replay
            if full_tiled is None:
                with torch.inference_mode():full=model(x)
                full_tiled=float((full-new).abs().max());assert full_tiled<1e-6
                del full
            pred=backend.session_prediction(seq,int(fi),np.array(s['centers']),s['expected_signed_dx_px']);ids=pred[:,0].astype(int);seeds=pred[:,1:3]
            region,offset=roi(raw,seeds,s['pitch_px']);reconroi=recon[offset[1]:offset[1]+region.shape[0],offset[0]:offset[0]+region.shape[1]].astype(float)
            images={'Raw':region,'Wiener':backend.wiener_contrast_restore(region,k,backend.NSR,pitch_px=s['pitch_px']),'MOSR':reconroi}
            for m,image in images.items():
                for r in measure(image,seeds-offset,ids,mc):
                    r['center_x_px']+=offset[0];r['center_y_px']+=offset[1]
                    b=baseline.loc[(seq,'R152' if m=='MOSR' else m,fi,r['pillar_id'])]
                    err=float(np.max(abs(np.array([r['center_x_px'],r['center_y_px'],r['radius_px']])-b[['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']].to_numpy(dtype=float))))
                    max_center_err=max(max_center_err,err);assert err<1e-7,err
                    rows.append(dict(sequence=seq,frame_index=int(fi),method=m,**r))
            records.append(dict(sequence=seq,frame_index=int(fi),source=str(source),source_sha256=receipt['source_sha256'],reconstruction_sha256=receipt['output_sha256'],fresh_reconstruction_max_difference=replay))
            if len(records)%10==0 or len(records)==86:save(OUT/'50x_status.json',dict(state='running',images=len(records),total=86,elapsed_seconds=time.perf_counter()-t0));print('50X_FRESH_INFERENCE_AND_LSC',len(records),'/86',flush=True)
    centers=pd.DataFrame(rows);centers.to_csv(OUT/'50x_centers.csv',index=False);idx=centers.set_index(['sequence','method','frame_index','pillar_id']).sort_index();steps=[]
    for p in pairs[pairs.magnification=='50x'].itertuples():
        for m in ['Raw','Wiener','MOSR']:
            a=idx.loc[(p.sequence,m,p.start_frame_index)].sort_index();b=idx.loc[(p.sequence,m,p.end_frame_index)].sort_index()
            value=abs(np.median((b.center_x_px-a.center_x_px).to_numpy()))*69
            steps.append(dict(sequence=p.sequence,method=m,start=int(p.start_frame_index),end=int(p.end_frame_index),step_nm=value))
    steps=pd.DataFrame(steps);steps.to_csv(OUT/'50x_steps.csv',index=False)
    stats=steps.groupby(['sequence','method']).step_nm.agg(n='count',mean_nm='mean',step_sd_nm='std').reset_index();assert stats.n.eq(30).all()
    stats.to_csv(OUT/'50x_condition_sd.csv',index=False)
    assert all(torch.equal(v.cpu(),params[k]) for k,v in model.named_parameters())
    # Verify the optional optical route remains reversible after the complete replay.
    patch=x[:,:,:256,:256]
    with torch.inference_mode():single=model.forward_tiled(patch)
    configure_optical_input(model,cfg,SRC,None);assert model.psf_fusion.count==25
    configure_optical_input(model,cfg,SRC,k)
    with torch.inference_mode():single_again=model.forward_tiled(patch)
    assert torch.equal(single,single_again)
    assert len(records)==86 and len(rows)==2322 and len(steps)==180
    save(OUT/'50x_complete.json',dict(passed=True,images=86,pairs_per_method=60,circles=len(rows),checkpoint_sha256=rec['sha256'],optical_installation=installed,full_vs_tiled_max_difference=full_tiled,max_fresh_reconstruction_difference=max(r['fresh_reconstruction_max_difference'] for r in records),max_remeasured_center_difference_px=max_center_err,learned_parameters_unchanged=True,single_psf_reinstallation_exact=True,excluded_pairs=0,source_records=records,statistics=stats.to_dict('records')))
    save(OUT/'50x_status.json',dict(state='complete',images=86,total=86,report='50x_complete.json'))
    print(stats.to_string(index=False),flush=True)

def lock():
    OUT.mkdir(parents=True,exist_ok=True)
    p=OUT/'protocol_lock.json';assert not p.exists(),'Existing lock: do not silently replace the protocol'
    save(p,dict(user_scope='20x thesis data, display each condition separately; recheck 50x reconstruction',created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),checkpoint_sha256=load(SRC/'results/final_audit.json')['checkpoint_sha256'],twenty_x='20260903, 30 full scans x 31 frames, nominal 1um, all 900 steps',fifty_x='original 20260702 0.5um and 1um, original 30 locked pairs each',reader='thesis normal-gradient geometric LSC with curvature reset per pillar; native objective settings 64 points at 20x and 96 points at 50x',wiener_nsr=.0565,twenty_x_scale_um_per_px=.1725,fifty_x_scale_um_per_px=.069,primary='one sample SD of 30 image-measured steps in each scan/condition; never combine objectives or nominal step conditions',twenty_x_summary='display all 30 per-scan SDs; pooled within-condition SD matches thesis report; each scan retains its identity',no_retraining=True,no_formal_baseline_changes=True,previous_radial720_results_retained=True))
    print(p)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['lock','20x','50x']);mode=ap.parse_args().mode
    if mode=='lock':lock()
    else:
        assert (OUT/'protocol_lock.json').exists()
        (run20 if mode=='20x' else run50)()
