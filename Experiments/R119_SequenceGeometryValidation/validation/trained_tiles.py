"""Check actual trained checkpoint parity on verified real Raw crops."""
from pathlib import Path
import json
import sys
import torch
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load,read,tiled

def main():
    model=load(ROOT/'runs/verified_physical_repair/weights/epoch_012.pth','cuda')
    config=json.loads((ROOT/'config/experiment.json').read_text());rows=[]
    with torch.inference_mode():
        for record in config['validation']['real_raw_inputs']:
            raw=read(ROOT/record['path']);x=torch.tensor(raw.astype(np.float32)/255)[None,None].cuda()
            full=model(x);cut=tiled(model,x,core=192)
            difference=(full-cut).abs()*255
            rows.append({'image':record['name'],'mean_gray':float(difference.mean()),'max_gray':float(difference.max()),
                         'p99_gray':float(torch.quantile(difference.flatten(),.99))})
    result={'status':'pass' if max(r['max_gray'] for r in rows)<.05 else 'fail','rows':rows}
    (ROOT/'validation/trained_tile_parity.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    if result['status']!='pass':raise RuntimeError('trained parity failed')
if __name__=='__main__':main()
