"""Re-measure every fixed frame with explicit curvature state, preserving original outputs."""
from pathlib import Path
import sys,json,time
import numpy as np
import pandas as pd
import skimage.segmentation.morphsnakes as ms
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/definition_audit';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
from probe_lsc_order import reset
SEQS=['50x_x_0p5um','50x_x_1um','20x_0p5um','20x_1um'];METHODS=['Raw','Wiener','V42','R152']
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    cfg=json.loads((ROOT/'sources/sequence_config.json').read_text(encoding='utf-8-sig'));locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv');backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv';rows=[];begin=time.perf_counter();ordinal=0
    for seq in SEQS:
        s=cfg['sequences'][seq];mag=s['magnification'];selected=locked[locked.sequence==seq];frameids=sorted(set(selected.start_frame_index)|set(selected.end_frame_index));pitch=s['pitch_px'];margin=int(np.ceil(.55*pitch));half=int(np.ceil(.46*pitch));normal=2.4 if mag=='20x' else 4.
        psf=backend.loadmat(backend.SWEEP_ROOT/f'{mag}_deconvolution_sweep.mat')['psf'];folder='20x' if mag=='20x' else '50x_calibrated'
        for fi in frameids:
            raw=backend.load_grayscale(Path(s['raw_dir'])/f'frame_{fi:04d}.bmp');pred=backend.session_prediction(seq,int(fi),np.array(s['centers'],float),s['expected_signed_dx_px'])
            x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(pred[:,1].max()))+margin+1);y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(pred[:,2].max()))+margin+1)
            r=raw[y0:y1,x0:x1];methods={'Raw':r,'Wiener':backend.wiener_contrast_restore(r,psf,backend.NSR,pitch_px=pitch),'V42':backend.load_grayscale(Path(s['v42_dir'])/f'frame_{fi:04d}.bmp')[y0:y1,x0:x1],'R152':np.load(ROOT/f'results/{folder}/reconstruction/{seq}/frame_{fi:04d}.npz')['output'][y0:y1,x0:x1].astype(float)}
            for method,image in methods.items():
                mi={'Raw':0,'Wiener':1,'V42':2,'R152':2}[method]
                for pi,(pid,x,y) in enumerate(pred):
                    patch,pc,origin=backend.crop_around(image,(x-x0,y-y0),half)
                    for phase in [0,1]:
                        reset(phase);v=backend.measure_inflection_lsc(patch,pc,s['radius_px'],sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=normal,polarity='dark')
                        radial=np.linalg.norm(v.inflection_points_xy-np.array([v.lsc.cx,v.lsc.cy]),axis=1)-v.lsc.radius
                        rows.append(dict(sequence=seq,magnification=mag,frame_index=int(fi),method=method,pillar_id=int(pid),phase=phase,predicted_legacy_phase=(ordinal*27+mi*9+pi)%2,lsc_center_x_px=v.lsc.cx+origin[0]+x0,lsc_center_y_px=v.lsc.cy+origin[1]+y0,lsc_radius_px=v.lsc.radius,radial_rms_nm=float(np.sqrt(np.mean(radial**2))*s['object_um_per_px']*1000),endpoint_count=int((np.linalg.norm(v.inflection_points_xy-v.coarse_contour_xy,axis=1)>=normal-1e-6).sum()),nonpositive_gradient_count=int((v.signed_gradient_strength<=0).sum()),sample_count=len(v.inflection_points_xy)))
            ordinal+=1
            if ordinal%10==0 or ordinal==166:
                save(OUT/'state_recheck_status.json',dict(state='running',frames=ordinal,total=166,center_rows=len(rows),elapsed_seconds=time.perf_counter()-begin));print('STATE RECHECK',ordinal,'/166',round(time.perf_counter()-begin,1),'sec',flush=True)
        pd.DataFrame(rows).to_csv(OUT/'state_centers_partial.csv',index=False)
    centers=pd.DataFrame(rows);centers.to_csv(OUT/'state_centers.csv',index=False);pairs=[]
    for phase in [0,1]:
        idx=centers[centers.phase==phase].set_index(['sequence','method','frame_index','pillar_id']).sort_index()
        for pair in locked.itertuples():
            s=cfg['sequences'][pair.sequence];scale=s['object_um_per_px']
            for m in METHODS:
                a=idx.loc[(pair.sequence,m,pair.start_frame_index)].sort_index();b=idx.loc[(pair.sequence,m,pair.end_frame_index)].sort_index()
                dx=(b.lsc_center_x_px.to_numpy()-a.lsc_center_x_px.to_numpy())*scale;dy=(b.lsc_center_y_px.to_numpy()-a.lsc_center_y_px.to_numpy())*scale;step=abs(np.median(dx));nom=s['nominal_step_um']
                pairs.append(dict(sequence=pair.sequence,magnification=s['magnification'],method=m,phase=phase,start=pair.start_frame_index,end=pair.end_frame_index,step_nm=step*1000,nominal_abs_error_nm=abs(step-nom)*1000,within_grid_sd_nm=np.std(dx,ddof=1)*1000,dy_nm=np.median(dy)*1000))
    pairs=pd.DataFrame(pairs);pairs.to_csv(OUT/'state_pairs.csv',index=False);summary=[]
    for (phase,m),g in pairs.groupby(['phase','method'],sort=False):
        for scope,seqs in [('all120',SEQS),('20x',SEQS[2:]),('50x',SEQS[:2])]+[(s,[s]) for s in SEQS]:
            h=g[g.sequence.isin(seqs)];summary.append(dict(phase=phase,method=m,scope=scope,n_pairs=len(h),step_sd_nm=np.mean([x.step_nm.std(ddof=1) for _,x in h.groupby('sequence')]),nominal_mae_nm=h.nominal_abs_error_nm.mean(),median_within_grid_sd_nm=h.within_grid_sd_nm.median()))
    summary=pd.DataFrame(summary);summary.to_csv(OUT/'state_summary.csv',index=False)
    original=pd.read_csv(ROOT/'results/full120/centers.csv');old=pd.read_csv(ROOT/'sources/historical_centers.csv');old=old[old.method=='MOSR'].copy();old['method']='V42';original=pd.concat([original,old]);keys=['sequence','method','frame_index','pillar_id'];cols=['lsc_center_x_px','lsc_center_y_px','lsc_radius_px']
    legacy=centers[centers.phase==centers.predicted_legacy_phase].set_index(keys).sort_index();original=original.set_index(keys).sort_index();assert legacy.index.equals(original.index)
    difference=abs(legacy[cols]-original[cols]).max();assert difference.max()<1e-7,difference
    zero=centers[centers.phase==0].set_index(keys).sort_index();one=centers[centers.phase==1].set_index(keys).sort_index();diff=one[cols]-zero[cols]
    effect=diff.reset_index();effect['scale']=effect.sequence.map(lambda s:cfg['sequences'][s]['object_um_per_px']*1000)
    effect['center_difference_nm']=np.hypot(effect.lsc_center_x_px,effect.lsc_center_y_px)*effect.scale;effect.to_csv(OUT/'state_center_effect.csv',index=False)
    assert len(centers)==11952 and len(pairs)==960
    result=dict(passed=True,frames=166,methods=METHODS,phases=[0,1],circle_fits=11952,pairs=960,original_phase_pattern_reproduces_all_four_methods=True,original_center_max_difference_px=difference.to_dict(),state_center_effect_max_nm=float(effect.center_difference_nm.max()),state_center_effect_mean_nm=float(effect.center_difference_nm.mean()),phase0='SI(IS(.)) first, reset per pillar; matches R152 native evaluation reset convention',phase1='IS(SI(.)) first, reset per pillar; sensitivity only',outcome='Order-sensitive coarse contour state confirmed; final LSC circle optimization itself is stateless.',original_results_preserved=True,elapsed_seconds=time.perf_counter()-begin)
    save(OUT/'state_recheck_complete.json',result);save(OUT/'state_recheck_status.json',dict(state='complete',**result));print(summary[summary.scope=='all120'].to_string(index=False));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
