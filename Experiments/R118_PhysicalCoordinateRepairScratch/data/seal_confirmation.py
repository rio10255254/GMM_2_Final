"""Build a separate confirmation set. No model predictions are made here."""
from pathlib import Path
import json
import hashlib
import sys
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.geometry import draw_mask,translate_high
from data.prepare import image_formation

def main():
    destination=ROOT/'data/confirmation'
    if (destination/'manifest.json').exists():raise FileExistsError('confirmation set is already sealed')
    destination.mkdir(parents=True,exist_ok=True)
    families=['circle','ellipse','rectangle','polygon','ring','crescent','lobed','thin_neck','thin_bar','dense_array','mixed_field','irregular_blob']
    records=[];cv2.setNumThreads(1)
    for i in range(144):
        seed=118990000+i*104729;rng=np.random.default_rng(seed);family=families[i%12]
        mask=draw_mask(256,8,family,rng)
        binary=(mask>127).astype(np.uint8)
        sdf=(cv2.distanceTransform(binary,cv2.DIST_L2,5)-cv2.distanceTransform(1-binary,cv2.DIST_L2,5))/8
        polarity=1 if (i//12)%2 else -1;width=float(rng.uniform(.45,1.15))
        lo=.2 if polarity>0 else .7;inside=lo+polarity*float(rng.uniform(.2,.45))
        reference=lo+(inside-lo)/(1+np.exp(-np.clip(sdf/width,-30,30)))
        sx=float(rng.uniform(.4,4.));meta={'sigma_x':sx,'sigma_y':float(sx*rng.uniform(.6,1.5)),
            'ghost_x':float(rng.uniform(-1.2,1.2)),'ghost_y':float(rng.uniform(-1.2,1.2)),
            'ghost_mix':float(rng.uniform(0,.1)),'broad_mix':float(rng.uniform(0,.2))}
        dx,dy=rng.uniform(-1.25,1.25,2);arrays={}
        for suffix,shift in [('a',(0.,0.)),('b',(dx,dy))]:
            high=translate_high(reference.astype(np.float32),*shift,8,cv2.INTER_LINEAR)
            source=cv2.resize(image_formation(high,meta),(256,256),interpolation=cv2.INTER_AREA)
            source+=rng.normal(0,1.5/255,source.shape).astype(np.float32)
            target=cv2.resize(high,(256,256),interpolation=cv2.INTER_AREA)
            arrays['source_'+suffix]=np.clip(source,0,1).astype(np.float16)
            arrays['target_'+suffix]=target.astype(np.float16)
        filename=f'{i:04d}.npz';np.savez_compressed(destination/filename,**arrays)
        records.append({'file':filename,'seed':seed,'family':family,'shift_xy':[float(dx),float(dy)],'sha256':hashlib.sha256((destination/filename).read_bytes()).hexdigest()})
    manifest={'status':'sealed_not_evaluated','use':'one final confirmation after design/model selection','independent_seed':True,
              'model_predictions_generated':False,'training_inclusion':False,'count':len(records),'records':records}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k!='records'}))
if __name__=='__main__':main()
