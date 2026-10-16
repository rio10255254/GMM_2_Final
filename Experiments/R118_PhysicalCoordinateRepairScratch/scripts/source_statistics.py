"""Read-only approximate noise statistics, not claimed PSF identification."""
from pathlib import Path
import hashlib
import json
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def main():
    config=json.loads((ROOT/'config/experiment.json').read_text());rows=[]
    for record in config['validation']['real_raw_inputs']:
        p=ROOT/record['path']
        if hashlib.sha256(p.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('not verified Raw')
        image=cv2.imdecode(np.fromfile(str(p),np.uint8),0).astype(np.float32)
        smooth=cv2.GaussianBlur(image,(0,0),2)
        gx=cv2.Sobel(smooth,cv2.CV_32F,1,0);gy=cv2.Sobel(smooth,cv2.CV_32F,0,1)
        magnitude=np.hypot(gx,gy);flat=magnitude<np.percentile(magnitude,30)
        lap=cv2.Laplacian(image,cv2.CV_32F,ksize=1)[flat]
        estimate=float(np.median(np.abs(lap-np.median(lap)))/(.67448975*np.sqrt(20)))
        rows.append({'name':record['name'],'source_sha256':record['sha256'],'estimated_noise_gray':estimate})
    result={'status':'complete','inputs_are_validation_crops':True,'no_pixels_copied_into_training':True,
            'method':'Laplacian MAD on lowest-gradient 30%; texture/correlation/quantization can bias this estimate',
            'optical_psf_independently_identified':False,'rows':rows}
    (ROOT/'validation/source_statistics.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
