"""Apply the independently selected radial LSC reader to all fixed real pairs."""
from pathlib import Path
import sys,json,time,hashlib
import numpy as np
import pandas as pd
sys.dont_write_bytecode=True
from localization_readers import radial_lsc
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/localization_improvement';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
PROJECT_ROOT = Path(__file__).resolve().parents[3]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    lock=load(OUT/'final_reader_lock.json');assert lock['selected_reader']=='radial_720_lsc'
    check=load(OUT/'real_content_validation_fresh.json');assert check['overall_passed']
    cfg=load(ROOT/'sources/sequence_config.json');locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv');backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv'
    old=pd.read_csv(ROOT/'results/definition_audit/state_centers.csv');old=old[(old.phase==0)&old.method.isin(['Raw','Wiener','R152'])].set_index(['sequence','method','frame_index','pillar_id']).sort_index()
    manifest=pd.read_csv(ROOT/'results/raw_frame_manifest.csv').set_index(['sequence','frame_index']);rows=[];start=time.perf_counter();count=0
    for seq,s in cfg['sequences'].items():
        selected=locked[locked.sequence==seq];ids=sorted(set(selected.start_frame_index)|set(selected.end_frame_index));mag=s['magnification'];pitch=s['pitch_px'];margin=int(np.ceil(.55*pitch));half=int(np.ceil(.46*pitch));folder='20x' if mag=='20x' else '50x_calibrated';psf=backend.loadmat(backend.SWEEP_ROOT/f'{mag}_deconvolution_sweep.mat')['psf']
        for fi in ids:
            source=Path(PROJECT_ROOT / s['raw_dir'])/f'frame_{fi:04d}.bmp';assert sha(source)==manifest.loc[(seq,fi),'sha256'];raw=backend.load_grayscale(source);pred=backend.session_prediction(seq,int(fi),np.array(s['centers'],float),s['expected_signed_dx_px'])
            x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(pred[:,1].max()))+margin+1);y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(pred[:,2].max()))+margin+1)
            rawroi=raw[y0:y1,x0:x1];path=ROOT/f'results/{folder}/reconstruction/{seq}/frame_{fi:04d}.npz';receipt=load(path.with_suffix('.json'));assert sha(path)==receipt['output_sha256']
            methods={'Raw':rawroi,'Wiener':backend.wiener_contrast_restore(rawroi,psf,backend.NSR,pitch_px=pitch),'R152':np.load(path)['output'][y0:y1,x0:x1].astype(float)}
            for method,image in methods.items():
                for pid,x,y in pred:
                    patch,pc,origin=backend.crop_around(image,(x-x0,y-y0),half);before=old.loc[(seq,method,fi,int(pid))];initial=np.array([before.lsc_center_x_px-origin[0]-x0,before.lsc_center_y_px-origin[1]-y0,before.lsc_radius_px]);c=radial_lsc(patch,initial,mag)
                    assert np.isfinite(c).all() and 0<c[2]<min(patch.shape)/2
                    rows.append(dict(sequence=seq,magnification=mag,frame_index=int(fi),method=method,pillar_id=int(pid),lsc_center_x_px=c[0]+origin[0]+x0,lsc_center_y_px=c[1]+origin[1]+y0,lsc_radius_px=c[2],old_center_x_px=before.lsc_center_x_px,old_center_y_px=before.lsc_center_y_px,center_change_nm=float(np.linalg.norm(c[:2]-initial[:2])*s['object_um_per_px']*1000)))
            count+=1
            if count%20==0 or count==166:print('IMPROVED LSC',count,'/166',round(time.perf_counter()-start,1),'sec',flush=True)
    centers=pd.DataFrame(rows);centers.to_csv(OUT/'improved_centers.csv',index=False);idx=centers.set_index(['sequence','method','frame_index','pillar_id']).sort_index();pairs=[]
    for row in locked.itertuples():
        scale=cfg['sequences'][row.sequence]['object_um_per_px']*1000;nom=row.nominal_step_um*1000
        for m in ['Raw','Wiener','R152']:
            a=idx.loc[(row.sequence,m,row.start_frame_index)].sort_index();b=idx.loc[(row.sequence,m,row.end_frame_index)].sort_index();dx=(b.lsc_center_x_px.to_numpy()-a.lsc_center_x_px.to_numpy())*scale;dy=(b.lsc_center_y_px.to_numpy()-a.lsc_center_y_px.to_numpy())*scale;step=abs(np.median(dx))
            pairs.append(dict(sequence=row.sequence,magnification=row.magnification,method=m,start=row.start_frame_index,end=row.end_frame_index,nominal_nm=nom,step_nm=step,nominal_abs_error_nm=abs(step-nom),within_grid_sd_nm=np.std(dx,ddof=1),dy_median_nm=np.median(dy),mean_step_nm=abs(dx.mean())))
    pairs=pd.DataFrame(pairs);pairs.to_csv(OUT/'improved_pairs.csv',index=False);summary=[]
    seqs=list(cfg['sequences'])
    for m,g in pairs.groupby('method',sort=False):
        for scope,ss in [('all120',seqs),('20x',seqs[2:]),('50x',seqs[:2])]+[(s,[s]) for s in seqs]:
            h=g[g.sequence.isin(ss)];summary.append(dict(scope=scope,method=m,n_pairs=len(h),step_sd_nm=np.mean([v.step_nm.std(ddof=1) for _,v in h.groupby('sequence')]),nominal_mae_nm=h.nominal_abs_error_nm.mean(),median_within_grid_sd_nm=h.within_grid_sd_nm.median()))
    summary=pd.DataFrame(summary);summary.to_csv(OUT/'improved_summary.csv',index=False)
    original=pd.read_csv(ROOT/'results/definition_audit/state_summary.csv');original=original[(original.phase==0)&original.method.isin(['Raw','Wiener','R152'])]
    compare=summary.merge(original,on=['scope','method','n_pairs'],suffixes=('_new','_old'))
    for key in ['step_sd_nm','nominal_mae_nm','median_within_grid_sd_nm']:compare[key+'_reduction_pct']=100*(compare[key+'_old']-compare[key+'_new'])/compare[key+'_old']
    compare.to_csv(OUT/'improvement_comparison.csv',index=False)
    assert count==166 and len(centers)==4482 and len(pairs)==360
    save(OUT/'real_complete.json',dict(passed=True,reader=lock['selected_reader'],frames=166,centers=4482,pairs=360,pairs_per_method=120,models=['Raw','Wiener','R152'],selection_before_real_scores=True,known_shift_validation_passed=True,trained_weights_changed=False,excluded_pairs=0,nominal_step_not_used_in_new_fitting=True,original_nominal_definition_preserved=True,source_script_sha256=sha(Path(__file__)),reader_sha256=sha(Path(__file__).with_name('localization_readers.py')),elapsed_seconds=time.perf_counter()-start))
    print(compare[compare.scope=='all120'].to_string(index=False),flush=True)
if __name__=='__main__':main()
