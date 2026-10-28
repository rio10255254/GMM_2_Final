"""Locked 20x-only evaluation with R152's unchanged native optical bank."""
from pathlib import Path
import sys, json, time
import numpy as np
import pandas as pd
import torch

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
MODEL_ROOT=Path('D:/GMM_2_Final/Experiments/R152_R148v2_SafeAdaptivePSF')
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
sys.path.insert(0,str(MODEL_ROOT))
from model import Model
from utils import setup, sha, load, save

OUT=ROOT/'results/20x'
OUT.mkdir(parents=True,exist_ok=True)

def main(magnification='20x',optical_mode='native'):
    global OUT
    assert magnification in ('20x','50x')
    mag=magnification
    sequences=['20x_0p5um','20x_1um'] if mag=='20x' else ['50x_x_0p5um','50x_x_1um']
    total=80 if mag=='20x' else 86
    if mag=='50x' and optical_mode=='native':
        authorization=load(ROOT/'config/shared_bank_authorization.json')
        assert authorization['use_unchanged_r152_bank_for_50x'] is True
        OUT=ROOT/'results/50x_shared_bank'; OUT.mkdir(parents=True,exist_ok=True)
    elif mag=='50x' and optical_mode=='objective':
        authorization=load(ROOT/'config/objective_optics_authorization.json')
        assert authorization['use_original_50x_calibration'] is True
        assert load(ROOT/'results/objective_adapter_preflight.json')['passed']
        OUT=ROOT/'results/50x_calibrated'; OUT.mkdir(parents=True,exist_ok=True)
    elif optical_mode!='native': raise ValueError('Unsupported optical mode')
    setup(1309001)
    for name,expected in load(MODEL_ROOT/'config/SOURCE_LOCK.json')['files'].items():
        assert sha(MODEL_ROOT/name)==expected,name
    cfg=load(MODEL_ROOT/'config/model.json'); lock=load(MODEL_ROOT/'calibration/BANK_LOCK.json')
    receipt=load(MODEL_ROOT/'runs/formal_8192/training_complete.json')['deployed_checkpoint']
    assert sha(receipt['path'])==receipt['sha256']
    assert sha(cfg['base_checkpoint'])==cfg['base_checkpoint_sha256']
    assert sha(MODEL_ROOT/cfg['psf_bank'])==lock['bank_sha256'] and lock['object_um_per_px']==0.1725
    device='cuda' if torch.cuda.is_available() else 'cpu'
    cp=torch.load(receipt['path'],map_location='cpu',weights_only=False)
    assert cp['model_config']==cfg
    model=Model(cfg,MODEL_ROOT).to(device).eval();model.load_state_dict(cp['model'],strict=True)
    assert float(model.deployment_scale)==1
    effective_bank_sha=lock['bank_sha256']; optical_receipt=None
    if optical_mode=='objective':
        from objective_optics import install_50x
        optical_receipt=install_50x(model,cfg,MODEL_ROOT)
        effective_bank_sha=optical_receipt['effective_bank_sha256']
        save(OUT/'optical_installation.json',optical_receipt)
    initial={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv'
    conf=load(ROOT/'sources/sequence_config.json')
    sel=pd.read_csv(ROOT/'sources/original_locked_pairs.csv')
    manifests=pd.read_csv(ROOT/'results/raw_frame_manifest.csv').set_index(['sequence','frame_index'])
    methods=['Raw','Wiener','R152'];rows=[];pairrows=[];outputs=[];begin=time.perf_counter()
    for seq in sequences:
        spec=conf['sequences'][seq]; pairs=sel[sel.sequence==seq].reset_index(drop=True)
        assert len(pairs)==30 and spec['magnification']==mag and spec['object_um_per_px']==(0.1725 if mag=='20x' else 0.069)
        frameids=sorted(set(pairs.start_frame_index)|set(pairs.end_frame_index))
        base=np.asarray(spec['centers'],float);pitch=float(spec['pitch_px']);radius=float(spec['radius_px']);scale=float(spec['object_um_per_px'])
        psf=np.asarray(backend.loadmat(backend.SWEEP_ROOT/f'{mag}_deconvolution_sweep.mat',squeeze_me=True)['psf'],float)
        for fi in frameids:
            source=Path(spec['raw_dir'])/f'frame_{fi:04d}.bmp'; expected=manifests.loc[(seq,fi),'sha256']
            assert sha(source)==expected
            raw=backend.load_grayscale(source)
            outputdir=OUT/'reconstruction'/seq;outputdir.mkdir(parents=True,exist_ok=True)
            output=outputdir/f'frame_{fi:04d}.npz';recpath=output.with_suffix('.json')
            if recpath.exists():
                rec=load(recpath)
                assert rec['checkpoint_sha256']==receipt['sha256'] and rec['source_sha256']==expected and rec['bank_sha256']==effective_bank_sha and sha(output)==rec['output_sha256']
                recon=np.load(output)['output']
            else:
                assert not output.exists(),f'Unreceipted output {output}'
                x=torch.from_numpy(raw.astype(np.float32)[None,None]).to(device)
                if device=='cuda':torch.cuda.synchronize()
                start=time.perf_counter()
                with torch.inference_mode(): y=model.forward_tiled(x)
                if device=='cuda':torch.cuda.synchronize()
                seconds=time.perf_counter()-start;recon=y.cpu().numpy()[0,0]
                assert recon.dtype==np.float32 and recon.shape==raw.shape and np.isfinite(recon).all()
                with output.open('xb') as f:np.savez_compressed(f,output=recon)
                rec=dict(sequence=seq,frame_index=int(fi),source=str(source),source_sha256=expected,output=str(output),output_sha256=sha(output),checkpoint_sha256=receipt['sha256'],bank_sha256=effective_bank_sha,object_um_per_px=scale,bank_calibration_um_per_px=scale if optical_mode=='objective' else 0.1725,optical_mode='objective-specific original 50x single PSF adapter' if optical_mode=='objective' else 'unchanged native 20x bank shared across objectives',deployment_scale=1,precision='FP32',tf32=False,core=512,halo=24,forward_seconds=seconds,device=device,shape=list(recon.shape))
                save(recpath,rec)
            outputs.append(rec)
            predicted=backend.session_prediction(seq,int(fi),base,float(spec['expected_signed_dx_px']))
            margin=int(np.ceil(.55*pitch)); half=int(np.ceil(.46*pitch))
            x0=max(0,int(np.floor(predicted[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(predicted[:,1].max()))+margin+1)
            y0=max(0,int(np.floor(predicted[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(predicted[:,2].max()))+margin+1)
            rawroi=raw[y0:y1,x0:x1]
            images={'Raw':rawroi,'Wiener':backend.wiener_contrast_restore(rawroi,psf,backend.NSR,pitch_px=pitch),'R152':recon[y0:y1,x0:x1].astype(np.float64)}
            for method,image in images.items():
                for pid,px,py in predicted:
                    patch,center,origin=backend.crop_around(image,(float(px-x0),float(py-y0)),half)
                    measurement=backend.measure_inflection_lsc(patch,center,radius,sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=2.4 if mag=='20x' else 4.0,polarity='dark')
                    rows.append(dict(sequence=seq,magnification=mag,frame_index=int(fi),method=method,pillar_id=int(pid),lsc_center_x_px=measurement.lsc.cx+origin[0]+x0,lsc_center_y_px=measurement.lsc.cy+origin[1]+y0,lsc_radius_px=measurement.lsc.radius,object_um_per_px=scale))
            if len(outputs)%10==0 or len(outputs)==total:
                save(OUT/'status.json',dict(state='running',images=len(outputs),total=total,elapsed_seconds=time.perf_counter()-begin))
                print('R152',mag,optical_mode,len(outputs),'/',total,round(time.perf_counter()-begin,1),'seconds',flush=True)
        centers=pd.DataFrame(rows); index=centers.set_index(['sequence','method','frame_index','pillar_id']).sort_index()
        for rank,pair in pairs.iterrows():
            for method in methods:
                a=index.loc[(seq,method,int(pair.start_frame_index))].loc[base[:,0].astype(int)]
                b=index.loc[(seq,method,int(pair.end_frame_index))].loc[base[:,0].astype(int)]
                dx=(b.lsc_center_x_px.to_numpy()-a.lsc_center_x_px.to_numpy())*scale
                dy=(b.lsc_center_y_px.to_numpy()-a.lsc_center_y_px.to_numpy())*scale
                shift=abs(np.median(dx)); nominal=spec['nominal_step_um']
                pairrows.append(dict(sequence=seq,magnification=mag,method=method,pair_rank_raw_locked=rank+1,start_frame_index=int(pair.start_frame_index),end_frame_index=int(pair.end_frame_index),nominal_step_um=nominal,aggregate_dx_um=float(np.median(dx)),aggregate_dy_um=float(np.median(dy)),measured_step_um=shift,nominal_abs_error_nm=abs(shift-nominal)*1000,within_grid_sd_nm=float(np.std(dx,ddof=1)*1000),cross_axis_abs_nm=abs(np.median(dy))*1000))
    centers=pd.DataFrame(rows); pairs=pd.DataFrame(pairrows)
    centers.to_csv(OUT/'centers.csv',index=False);pairs.to_csv(OUT/'per_pair.csv',index=False)
    stats=[]
    for (seq,m),g in pairs.groupby(['sequence','method'],sort=False):
        stats.append(dict(sequence=seq,method=m,n_pairs=len(g),step_sd_nm=g.measured_step_um.std(ddof=1)*1000,nominal_mae_nm=g.nominal_abs_error_nm.mean(),median_within_grid_sd_nm=g.within_grid_sd_nm.median()))
    summary=pd.DataFrame(stats)
    for m in methods:
        g=pairs[pairs.method==m];s=summary[summary.method==m]
        stats.append(dict(sequence=f'{mag}_only_two_conditions',method=m,n_pairs=60,step_sd_nm=s.step_sd_nm.mean(),nominal_mae_nm=s.nominal_mae_nm.mean(),median_within_grid_sd_nm=g.within_grid_sd_nm.median()))
    pd.DataFrame(stats).to_csv(OUT/'summary.csv',index=False)
    old=pd.read_csv(ROOT/'sources/historical_per_pair.csv'); keys=['sequence','method','pair_rank_raw_locked'];cols=['measured_step_um','nominal_abs_error_nm','within_grid_sd_nm']
    new=pairs[pairs.method.isin(['Raw','Wiener'])].set_index(keys).sort_index()
    old=old[old.method.isin(['Raw','Wiener'])&old.sequence.isin(sequences)].set_index(keys).sort_index()
    assert old.index.equals(new.index)
    delta=abs(old[cols]-new[cols]).max();assert delta.max()<1e-7,delta
    unchanged=all(torch.equal(initial[k],v.cpu()) for k,v in model.state_dict().items());assert unchanged
    assert len(outputs)==total and len(centers)==total*27 and len(pairs)==180
    complete=dict(state=f'complete_{mag}_only',images=total,pairs_per_method=60,center_rows=total*27,pair_rows=180,source_scope=f'Original {mag} conditions; {optical_mode} optics',checkpoint_sha256=receipt['sha256'],bank_sha256=effective_bank_sha,learned_weights_unchanged=True,weights_and_buffers_unchanged=unchanged,optical_installation=optical_receipt,raw_wiener_original_pair_max_difference=delta.to_dict(),native_fp32_output=True,postprocessing=False,full_50x_pending=mag=='20x',elapsed_seconds=time.perf_counter()-begin)
    save(OUT/'complete.json',complete)
    save(OUT/'status.json',complete)
    save(OUT/'reconstruction_manifest.json',outputs)
    print(pd.DataFrame(stats).to_string(index=False),flush=True)

if __name__=='__main__':main()
