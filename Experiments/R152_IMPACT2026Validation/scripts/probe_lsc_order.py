"""Check whether the legacy contour reader retains order-sensitive curvature state."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
import skimage.segmentation.morphsnakes as ms
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/definition_audit';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
def reset(phase):
    ops=[lambda x:ms.sup_inf(ms.inf_sup(x)),lambda x:ms.inf_sup(ms.sup_inf(x))]
    ms._curvop=ms._fcycle(ops[phase:]+ops[:phase])
def main():
    cfg=json.loads((ROOT/'sources/sequence_config.json').read_text(encoding='utf-8-sig'));locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv');backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv';rows=[]
    for seq,s in cfg['sequences'].items():
        fi=int(locked[locked.sequence==seq].iloc[0].start_frame_index);mag=s['magnification'];raw=backend.load_grayscale(Path(s['raw_dir'])/f'frame_{fi:04d}.bmp');pred=backend.session_prediction(seq,fi,np.array(s['centers'],float),s['expected_signed_dx_px']);pitch=s['pitch_px'];margin=int(np.ceil(.55*pitch));half=int(np.ceil(.46*pitch))
        x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(raw.shape[1],int(np.ceil(pred[:,1].max()))+margin+1);y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(raw.shape[0],int(np.ceil(pred[:,2].max()))+margin+1)
        r=raw[y0:y1,x0:x1];psf=backend.loadmat(backend.SWEEP_ROOT/f'{mag}_deconvolution_sweep.mat')['psf'];folder='20x' if mag=='20x' else '50x_calibrated'
        methods={'Raw':r,'Wiener':backend.wiener_contrast_restore(r,psf,backend.NSR,pitch_px=pitch),'V42':backend.load_grayscale(Path(s['v42_dir'])/f'frame_{fi:04d}.bmp')[y0:y1,x0:x1],'R152':np.load(ROOT/f'results/{folder}/reconstruction/{seq}/frame_{fi:04d}.npz')['output'][y0:y1,x0:x1].astype(float)}
        for method,image in methods.items():
            for pid,x,y in pred:
                patch,pc,origin=backend.crop_around(image,(x-x0,y-y0),half);values=[]
                for phase in [0,1]:
                    reset(phase);v=backend.measure_inflection_lsc(patch,pc,s['radius_px'],sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=2.4 if mag=='20x' else 4.,polarity='dark');values.append(np.array([v.lsc.cx,v.lsc.cy,v.lsc.radius]))
                d=(values[1]-values[0])*s['object_um_per_px']*1000
                rows.append(dict(sequence=seq,frame=fi,method=method,pillar_id=int(pid),phase_x_difference_nm=d[0],phase_y_difference_nm=d[1],phase_radius_difference_nm=d[2],phase_center_distance_nm=np.linalg.norm(d[:2])))
    df=pd.DataFrame(rows);df.to_csv(OUT/'curvature_order_probe.csv',index=False)
    print(df.groupby(['sequence','method']).phase_center_distance_nm.agg(['mean','max']).to_string())
    print('overall_max_nm',df.phase_center_distance_nm.max())
if __name__=='__main__':main()
