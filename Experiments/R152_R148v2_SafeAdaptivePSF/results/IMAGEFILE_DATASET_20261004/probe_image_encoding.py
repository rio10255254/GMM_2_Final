"""Check every source image value before selecting the actual image storage codec."""
import json
from pathlib import Path
import numpy as np

SOURCE=Path(r'D:\GMM_2_Final\Deliverables\R152_Standalone_20261004/data')
OUT=Path(__file__).resolve().parent

def main():
    minimum={};maximum={};count=0;failures=0
    for i,path in enumerate(sorted(SOURCE.rglob('*.npz')),1):
        with np.load(path,allow_pickle=False) as z:
            for key in ('target','noiseless'):
                a=z[key]
                minimum[key]=min(minimum.get(key,1),float(a.min()))
                maximum[key]=max(maximum.get(key,0),float(a.max()))
                assert np.isfinite(a).all() and a.min()>=0 and a.max()<=1
                encoded=np.rint(a.astype(np.float64)*65535).astype(np.uint16)
                decoded=(encoded.astype(np.float64)/65535).astype(np.float16)
                failures+=int(np.count_nonzero(decoded!=a));count+=a.size
        if i%128==0:print('PROBE',i,'/768',flush=True)
    result=dict(minimum=minimum,maximum=maximum,image_values=count,PNG16_original_FP16_roundtrip_mismatches=failures)
    (OUT/'image_encoding_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
