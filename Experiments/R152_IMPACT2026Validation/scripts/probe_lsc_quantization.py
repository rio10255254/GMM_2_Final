"""Match R152 display precision to historical V42 while holding the corrected reader fixed."""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/definition_audit'
sys.path.insert(0,str(ROOT/'sources'))
import run_displacement_lsc as backend
from probe_lsc_order import reset
def main():
    cfg=json.loads((ROOT/'sources/sequence_config.json').read_text(encoding='utf-8-sig'));locked=pd.read_csv(ROOT/'sources/original_locked_pairs.csv');backend.SESSION_TABLE=ROOT/'sources/session_anchors.csv';rows=[]
    for seq,s in cfg['sequences'].items():
        mag=s['magnification'];sel=locked[locked.sequence==seq];ids=sorted(set(sel.start_frame_index)|set(sel.end_frame_index));pitch=s['pitch_px'];half=int(np.ceil(.46*pitch));folder='20x' if mag=='20x' else '50x_calibrated'
        for fi in ids:
            image=np.load(ROOT/f'results/{folder}/reconstruction/{seq}/frame_{fi:04d}.npz')['output'];image=np.rint(image.astype(np.float64)*255).clip(0,255)/255
            pred=backend.session_prediction(seq,int(fi),np.array(s['centers'],float),s['expected_signed_dx_px'])
            # Match original nested ROI/pillar cropping, including floor/ceil boundaries.
            margin=int(np.ceil(.55*pitch));x0=max(0,int(np.floor(pred[:,1].min()))-margin);x1=min(image.shape[1],int(np.ceil(pred[:,1].max()))+margin+1);y0=max(0,int(np.floor(pred[:,2].min()))-margin);y1=min(image.shape[0],int(np.ceil(pred[:,2].max()))+margin+1);image=image[y0:y1,x0:x1]
            for pid,x,y in pred:
                patch,pc,origin=backend.crop_around(image,(x-x0,y-y0),half);reset(0)
                v=backend.measure_inflection_lsc(patch,pc,s['radius_px'],sample_count=64 if mag=='20x' else 96,acm_iterations=13 if mag=='20x' else 15,normal_half_width_px=2.4 if mag=='20x' else 4.,polarity='dark')
                rows.append(dict(sequence=seq,frame_index=int(fi),pillar_id=int(pid),x=v.lsc.cx+origin[0]+x0,y=v.lsc.cy+origin[1]+y0))
    centers=pd.DataFrame(rows);centers.to_csv(OUT/'r152_u8_centers.csv',index=False);idx=centers.set_index(['sequence','frame_index','pillar_id']).sort_index();pairs=[]
    for p in locked.itertuples():
        a=idx.loc[(p.sequence,p.start_frame_index)].sort_index();b=idx.loc[(p.sequence,p.end_frame_index)].sort_index();scale=cfg['sequences'][p.sequence]['object_um_per_px']*1000;dx=(b.x.to_numpy()-a.x.to_numpy())*scale;step=abs(np.median(dx));pairs.append(dict(sequence=p.sequence,start=p.start_frame_index,end=p.end_frame_index,step_nm=step,nominal_abs_error_nm=abs(step-p.nominal_step_um*1000),within_grid_sd_nm=np.std(dx,ddof=1)))
    pairs=pd.DataFrame(pairs);pairs.to_csv(OUT/'r152_u8_pairs.csv',index=False)
    result=dict(method='R152 quantized to uint8 for diagnostic only',state_reset_phase=0,step_sd_nm=float(np.mean([g.step_nm.std(ddof=1) for _,g in pairs.groupby('sequence')])),nominal_mae_nm=float(pairs.nominal_abs_error_nm.mean()),median_within_grid_sd_nm=float(pairs.within_grid_sd_nm.median()),n_pairs=120)
    (OUT/'r152_u8_summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
