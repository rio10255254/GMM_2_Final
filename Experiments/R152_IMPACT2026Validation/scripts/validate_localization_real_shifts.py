"""Known shifts of actual image content, before using real nominal-step outcomes."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
from scipy import ndimage
sys.dont_write_bytecode=True
from localization_readers import baseline,radial_lsc,intensity_circle,pair_translation
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/localization_improvement'
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
def main(extended=False,fresh=False):
    cfg=json.loads((ROOT/'sources/sequence_config.json').read_text(encoding='utf-8-sig'));locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv');backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv';rows=[];rng=np.random.default_rng(50631)
    shifts=[(0.,0.),(1.,0.),(-1.,0.),(.17,.11),(.43,-.21),(.79,.13),(-.31,-.17),(-.67,.23)]
    if fresh:
        shifts=[(0.,0.),(1.,0.),(-1.,0.),(.29,-.13),(.58,.23),(.91,-.09),(-.47,.07),(-.82,-.19)]
        rng=np.random.default_rng(62091)
    for seq,s in cfg['sequences'].items():
        selected=locked[locked.sequence==seq];fi=int(selected.iloc[len(selected)//2 if fresh else 0].start_frame_index);mag=s['magnification'];raw=backend.load_grayscale(Path(s['raw_dir'])/f'frame_{fi:04d}.bmp');pred=backend.session_prediction(seq,fi,np.array(s['centers'],float),s['expected_signed_dx_px']);pitch=s['pitch_px'];margin=int(np.ceil(.55*pitch));half=int(np.ceil(.46*pitch))
        x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(pred[:,1].max()))+margin+1);y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(pred[:,2].max()))+margin+1)
        r=raw[y0:y1,x0:x1];psf=backend.loadmat(backend.SWEEP_ROOT/f'{mag}_deconvolution_sweep.mat')['psf'];folder='20x' if mag=='20x' else '50x_calibrated'
        methods={'Raw':r,'Wiener':backend.wiener_contrast_restore(r,psf,backend.NSR,pitch_px=pitch),'R152':np.load(ROOT/f'results/{folder}/reconstruction/{seq}/frame_{fi:04d}.npz')['output'][y0:y1,x0:x1].astype(float)}
        for method,image in methods.items():
            for pid,x,y in pred:
                if int(pid) not in ([23,28,35] if fresh else [22,29,36]):continue
                patch,seed,_=backend.crop_around(image,(x-x0,y-y0),half);ca=baseline(patch,seed,s['radius_px'],mag)
                base_est={'fixed_state_lsc':ca,'radial_720_lsc':radial_lsc(patch,ca,mag),'radial_intensity_fit':intensity_circle(patch,ca)}
                pad=32;padded_field=np.pad(patch,pad,mode='reflect');spectrum=np.fft.fftn(padded_field)
                for dx,dy in shifts:
                    shifted=np.fft.ifftn(ndimage.fourier_shift(spectrum,[dy,dx])).real[pad:-pad,pad:-pad];cb=baseline(shifted,np.array(seed)+[dx,dy]+rng.uniform(-.3,.3,2),s['radius_px'],mag)
                    estimates={'fixed_state_lsc':cb,'radial_720_lsc':radial_lsc(shifted,cb,mag),'radial_intensity_fit':intensity_circle(shifted,cb)}
                    if extended:
                        estimates['paired_translation_background_plane']=np.r_[ca[:2]+pair_translation(patch,shifted,ca[:2],cb[:2]-ca[:2],s['radius_px'],background_plane=True),ca[2]]
                        base_est['paired_translation_background_plane']=ca
                    for reader,v in estimates.items():
                        d=v[:2]-base_est[reader][:2];error=d-[dx,dy]
                        rows.append(dict(sequence=seq,method=method,pillar_id=int(pid),reader=reader,dx_true=dx,dy_true=dy,dx_error_px=error[0],dy_error_px=error[1],vector_error_px=np.linalg.norm(error),vector_error_nm=np.linalg.norm(error)*s['object_um_per_px']*1000))
    suffix='_fresh' if fresh else '_v2' if extended else ''
    df=pd.DataFrame(rows);df.to_csv(OUT/f'real_content_known_shifts{suffix}.csv',index=False)
    summary=df.groupby(['reader','method']).vector_error_px.agg(['mean','median','max']).reset_index();summary.to_csv(OUT/f'real_content_shift_summary{suffix}.csv',index=False)
    selected=json.loads((OUT/('final_reader_lock.json' if fresh else 'reader_selection_lock.json')).read_text())['selected_reader'];overall=df.groupby('reader').vector_error_px.mean();passed=bool(overall[selected]<overall['fixed_state_lsc'])
    if fresh:
        by_method=df.groupby(['reader','method']).vector_error_px.mean().unstack();passed=bool((by_method.loc[selected]<=by_method.loc['fixed_state_lsc']).all())
    report=dict(selected_reader=selected,known_shift_cases=len(df)//3,overall_mean_vector_error_px=overall.to_dict(),overall_passed=passed,per_method=summary.to_dict('records'),real120_scores_used=False,limitation='Digital Fourier shifts test estimator sensitivity on actual content, not an independent physical displacement calibration.')
    (OUT/f'real_content_validation{suffix}.json').write_text(json.dumps(report,indent=2)+'\n');print(summary.to_string(index=False));print('overall_passed',passed)
if __name__=='__main__':main()
