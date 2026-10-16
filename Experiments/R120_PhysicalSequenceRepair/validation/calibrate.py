from pathlib import Path
import sys
import json
import numpy as np
from scipy.ndimage import gaussian_filter, shift
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from validation.registration import estimate,summarize


def fixtures():
    y,x=np.mgrid[:128,:128].astype(float)
    ref=.12+.72*np.exp(-3*((x-67)/25)**2-3*((y-62)/19)**2)+.08*np.exp(-((x-35)/8)**2-((y-91)/7)**2)
    rows=[]
    for dx,dy in [(0,0),(1,0),(-1,0),(0,1),(0,-1),(.5,.5),(-.5,-.5),(.125,0)]:
        # Continuous shifted analytic truth avoids a self-fulfilling interpolation fixture.
        obs=.12+.72*np.exp(-3*((x-dx-67)/25)**2-3*((y-dy-62)/19)**2)+.08*np.exp(-((x-dx-35)/8)**2-((y-dy-91)/7)**2)
        measured=estimate(obs,ref)
        error=float(np.max(np.abs(np.asarray(measured['xy'])-[dx,dy]))) if measured['valid'] else None
        rows.append({'case':f'shift_{dx}_{dy}','result':measured,'error':error,'pass':measured['valid'] and error<.08})
    for label,obs,target in [('gain_offset',ref*1.12+.02,ref),('saturated_gain',np.clip(ref*1.3+.1,0,1),ref),
                              ('symmetric_blur',gaussian_filter(ref,1.2),ref),('dark',1-ref,1-ref)]:
        measured=estimate(obs,target)
        error=float(np.linalg.norm(measured['xy'])) if measured['valid'] else None
        rows.append({'case':label,'result':measured,'error':error,'pass':measured['valid'] and error<.08})
    for label,obs,target in [('flat',np.ones_like(ref)*.4,ref),('axis',np.tile(np.linspace(.1,.9,128),(128,1)),np.tile(np.linspace(.1,.9,128),(128,1))),('crop',ref[:-3],ref)]:
        measured=estimate(obs,target)
        rows.append({'case':label,'result':measured,'pass':not measured['valid']})
    result={'status':'pass' if all(r['pass'] for r in rows) else 'fail','fixtures':rows,
            'scope':'all validity and photometry cases contribute to status; no relaxed tolerance'}
    return result


if __name__=='__main__':
    result=fixtures();folder=ROOT/'results';folder.mkdir(exist_ok=True)
    path=folder/'calibration.json'
    with path.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2));raise SystemExit(0 if result['status']=='pass' else 2)
