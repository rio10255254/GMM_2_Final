"""Verify fixed previews are exact crops of the preserved camera acquisitions."""
import argparse
import hashlib
from pathlib import Path
from four_round_recovery_common import read_json, sha, write_json

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--catalog',type=Path)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.exists():raise FileExistsError('Keep previous camera provenance verification')
    import cv2
    import numpy as np
    cv2.setNumThreads(1)
    catalog=read_json(a.catalog or a.root/'docs/reproducibility/four_rounds/PREVIEW_CAMERA_ORIGINS.json')
    checked=[]
    for record in catalog['previews']:
        source=a.root/record['original_camera_source']
        if sha(source)!=record['original_camera_sha256']:raise ValueError('Camera original differs')
        raw=cv2.imdecode(np.fromfile(source,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        if raw is None:raise ValueError('Unreadable camera original')
        x,y,w,h=record['crop_xywh']
        if min(x,y)<0 or min(w,h)<=0 or x+w>raw.shape[1] or y+h>raw.shape[0]:raise ValueError('Invalid crop')
        crop=raw[y:y+h,x:x+w]
        ok,encoded=cv2.imencode('.bmp',crop)
        if not ok:raise ValueError('Cannot encode historical crop')
        digest=hashlib.sha256(encoded.tobytes()).hexdigest()
        if digest!=record['preview_sha256']:raise ValueError('Recreated preview bytes differ')
        for rel in record['all_four_rounds_preview_paths']:
            actual=a.root/rel
            if sha(actual)!=digest:raise ValueError('Preserved preview differs from camera crop')
            checked.append(rel)
    if len(checked)!=16:raise ValueError('Expected four camera views across four rounds')
    a.report.parent.mkdir(parents=True,exist_ok=True)
    write_json(a.report,{'status':'PASS','original_camera_frames':4,'exact_preview_files':16,
        'pixels_and_encoded_BMP_bytes_exact':True,'no_model_used_to_generate_previews':True,'files':checked})
    print('FOUR_ORIGINAL_CAMERA_FRAMES_RECREATE_ALL_16_PREVIEWS_EXACTLY',flush=True)

if __name__=='__main__':main()
