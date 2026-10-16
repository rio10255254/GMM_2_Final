"""Fixed physical phase probe, independent registration; no confirmation."""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from collections import defaultdict
import argparse
import csv
import hashlib
import json
import os
import sys
import time
import cv2
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load
from validation.registration import estimate


def measured(job):
    index,source,target=job
    return index,estimate(source,target)


def worker_init():
    cv2.setNumThreads(1)
    from threadpoolctl import threadpool_limits
    threadpool_limits(1)


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=['diagnostic','all'],default='diagnostic');args=p.parse_args()
    torch.set_num_threads(4);cv2.setNumThreads(1)
    ds=ROOT/'data/sequences/validation';manifest=json.loads((ds/'manifest.json').read_text())
    # Fixed 1/8, 1/2, whole-pixel x shifts and y/diagonal cases selected before
    # inspecting probe outcomes. Full 49-position payload remains available.
    selected={(0.,0.),(.125,0.),(-.125,0.),(.5,0.),(-.5,0.),(1.,0.),(-1.,0.),
              (0.,.5),(0.,-.5),(.5,.5),(-.5,-.5)}
    models={'Raw':None}
    for seed in [1185001,1185002]:
        for arm in ['A','B']:
            name=f'{arm}_s{seed}';path=ROOT/f'runs/probe_{name}/weights/epoch_012.pth'
            if not path.exists():raise FileNotFoundError(path)
            models[name]=load(path,'cuda')
    out=ROOT/'results/motion_diagnostic';out.mkdir(exist_ok=False)
    rows=[];hashes={};start=time.monotonic()
    with ProcessPoolExecutor(max_workers=4,initializer=worker_init) as pool:
        for r in manifest['records']:
            with np.load(ds/r['file']) as f:
                indexes=[i for i,xy in enumerate(f['xy']) if args.profile=='all' or tuple(xy) in selected]
                source=f['source'][indexes].astype(np.float32);truth=f['target'][indexes].astype(np.float32)/255
                xy=f['xy'][indexes]
            rng=np.random.default_rng(1208001+r['scene_index'])
            source=np.clip(source+rng.normal(0,1.5/255,source.shape).astype(np.float32),0,1)
            # Every model consumes these identical arrays. No per-model exposure.
            input_sha=hashlib.sha256(source.tobytes()).hexdigest();hashes[str(r['scene_index'])]=input_sha
            tensor=torch.from_numpy(source)[:,None].cuda()
            for name,model in models.items():
                if model is None:output=source
                else:
                    with torch.inference_mode():output=model(tensor).cpu().numpy()[:,0]
                results=list(pool.map(measured,[(i,output[i],truth[i]) for i in range(len(output))]))
                for i,position in results:
                    rows.append({'method':name,'scene_id':r['scene_index'],'family':r['family'],'polarity':r['polarity'],
                        'dx':float(xy[i,0]),'dy':float(xy[i,1]),'input_sha256':input_sha,
                        'valid':position['valid'],'failure_reason':None if position['valid'] else position['reason'],
                        'error_x_px':position['xy'][0] if position['valid'] else None,
                        'error_y_px':position['xy'][1] if position['valid'] else None,
                        'mae_gray':float(np.abs(output[i]-truth[i]).mean()*255)})
            print(json.dumps({'scenes':len(hashes),'total':len(manifest['records']),'elapsed_seconds':round(time.monotonic()-start)}),flush=True)
    with (out/'per_view.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary=[]
    for name in models:
        chosen=[r for r in rows if r['method']==name];valid=[r for r in chosen if r['valid']]
        groups=defaultdict(list)
        for row in valid:groups[row['scene_id']].append(row)
        spreads=[]
        for values in groups.values():
            if len(values)>1:spreads.append(np.std([[r['error_x_px'],r['error_y_px']] for r in values],axis=0,ddof=1))
        summary.append({'method':name,'views':len(chosen),'invalid_views':len(chosen)-len(valid),
            'median_mae_gray':float(np.median([r['mae_gray'] for r in chosen])),
            'median_residual_position_px':float(np.median([np.hypot(r['error_x_px'],r['error_y_px']) for r in valid])) if valid else None,
            'median_scene_phase_sensitivity_xy_px':np.median(spreads,axis=0).tolist() if spreads else None})
    report={'status':'complete','profile':args.profile,'models':summary,'input_hashes':hashes,
        'interpretation':'registration against each correctly shifted target; ideal residual is zero, not dx/dy. Phase sensitivity is NOT static repeat SD or real LSC step SD.',
        'scope':'development diagnostic only; no ACM/model promotion claim'}
    (out/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
