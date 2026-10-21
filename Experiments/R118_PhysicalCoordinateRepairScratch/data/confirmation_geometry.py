"""Add reproducible geometric truth without changing sealed observations."""
from pathlib import Path
import hashlib
import json
import sys
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from data.geometry import draw_mask,translate_high

def main():
    directory=ROOT/'data/confirmation';path=directory/'manifest.json';manifest=json.loads(path.read_text())
    if manifest['model_predictions_generated']:raise RuntimeError('confirmation has already been evaluated')
    cv2.setNumThreads(1)
    for record in manifest['records']:
        rng=np.random.default_rng(record['seed']);high=draw_mask(256,8,record['family'],rng)
        binary=(high>127).astype(np.uint8)
        sdf=(cv2.distanceTransform(binary,cv2.DIST_L2,5)-cv2.distanceTransform(1-binary,cv2.DIST_L2,5))/8
        coverage=high.astype(np.float32)/255;arrays={}
        for suffix,shift in [('a',(0.,0.)),('b',record['shift_xy'])]:
            for key,value in [('mask',coverage),('sdf',sdf)]:
                moved=translate_high(value,*shift,8,cv2.INTER_LINEAR)
                arrays[key+'_'+suffix]=cv2.resize(moved,(256,256),interpolation=cv2.INTER_AREA).astype(np.float16)
        relative='geometry/'+record['file'];destination=directory/relative;destination.parent.mkdir(exist_ok=True)
        if not destination.exists():np.savez_compressed(destination,**arrays)
        record['geometry_file']=relative
        record['geometry_sha256']=hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest['geometric_truth_complete']=True
    manifest['sealed_observations_modified']=False
    path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'count':len(manifest['records']),'geometry_complete':True,'observations_modified':False,'model_evaluation_performed':False}))
if __name__=='__main__':main()
