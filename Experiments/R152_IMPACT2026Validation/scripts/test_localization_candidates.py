"""Select readout from known translations before revealing real nominal-step scores."""
from pathlib import Path
import json,sys,time
import numpy as np
import pandas as pd
from scipy import special
sys.dont_write_bytecode=True
from localization_readers import baseline,radial_lsc,intensity_circle,pair_translation
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/localization_improvement';OUT.mkdir(parents=True,exist_ok=True)

def image(size,center,radius,sigma,rng,noise,gradient):
    # Analytic smooth circle, integrated over detector pixels on a 4x4 subpixel grid.
    yy,xx=np.mgrid[:size,:size];value=np.zeros((size,size))
    for dy in [-.375,-.125,.125,.375]:
        for dx in [-.375,-.125,.125,.375]:
            distance=np.hypot(xx+dx-center[0],yy+dy-center[1]);value+=.72-.48*.5*special.erfc((distance-radius)/(np.sqrt(2)*sigma))
    value/=16;value+=gradient[0]*(xx-size/2)/size+gradient[1]*(yy-size/2)/size
    return value+rng.normal(0,noise,value.shape)

def run(split,extended=False):
    rng=np.random.default_rng(30217 if split=='development' else 819273);rows=[]
    shifts=[(.17,.11),(.63,-.08),(1.3,.04),(3.7,-.13),(8.6,.07),(14.2,-.19)] if split=='development' else [(.31,-.17),(.82,.13),(2.17,-.06),(5.27,.18),(7.73,-.11),(13.63,.09)]
    for mag,radius,default_size in [('20x',7.6,64),('50x',19.5,96)]:
        for sigma in [.6,1.4,2.3]:
            for shift in shifts:
                for noise in [0.,.006]:
                    c=np.array([default_size*.40,default_size*.50])+rng.uniform(-.5,.5,2);d=np.array(shift)
                    a=image(default_size,c,radius,sigma,rng,noise,[.03,-.02]);b=image(default_size,c+d,radius,sigma*1.03,rng,noise,[-.01,.025])*1.015+.007
                    # Seeds only locate a local patch; they are intentionally perturbed.
                    ca=baseline(a,c+rng.uniform(-.35,.35,2),radius,mag);cb=baseline(b,c+d+rng.uniform(-.35,.35,2),radius,mag)
                    readers={'fixed_state_lsc':cb[:2]-ca[:2]}
                    readers['radial_720_lsc']=radial_lsc(b,cb,mag)[:2]-radial_lsc(a,ca,mag)[:2]
                    readers['radial_intensity_fit']=intensity_circle(b,cb)[:2]-intensity_circle(a,ca)[:2]
                    readers['paired_photometric_translation']=pair_translation(a,b,ca[:2],cb[:2]-ca[:2],radius)
                    if extended:readers['paired_translation_background_plane']=pair_translation(a,b,ca[:2],cb[:2]-ca[:2],radius,background_plane=True)
                    for name,actual in readers.items():rows.append(dict(split=split,mag=mag,radius=radius,sigma=sigma,noise=noise,dx_true=d[0],dy_true=d[1],reader=name,dx_est=actual[0],dy_est=actual[1],dx_error_px=actual[0]-d[0],dy_error_px=actual[1]-d[1],vector_error_px=float(np.linalg.norm(actual-d))))
    return pd.DataFrame(rows)
def main():
    t=time.perf_counter();dev=run('development');dev.to_csv(OUT/'synthetic_development.csv',index=False)
    scores=dev.groupby('reader').vector_error_px.agg(['mean','median','max']).sort_values('mean');selected=scores.index[0]
    lock=dict(selected_reader=selected,selection='lowest known-translation mean vector error on synthetic development only',real120_scores_used=False,candidate_scores=scores.reset_index().to_dict('records'),plan='config/LOCALIZATION_IMPROVEMENT_PLAN.json')
    (OUT/'reader_selection_lock.json').write_text(json.dumps(lock,indent=2)+'\n')
    print('LOCK',json.dumps(lock,indent=2),flush=True)
    test=run('heldout');test.to_csv(OUT/'synthetic_heldout.csv',index=False)
    summary=pd.concat([dev,test]).groupby(['split','reader','mag']).vector_error_px.agg(['mean','median','max']).reset_index();summary.to_csv(OUT/'synthetic_summary.csv',index=False)
    print(summary.to_string(index=False));print('seconds',time.perf_counter()-t)
if __name__=='__main__':main()
