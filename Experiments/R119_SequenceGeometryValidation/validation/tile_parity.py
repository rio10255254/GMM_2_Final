"""Compare direct and halo-tiled R119 inference on verified Raw previews."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import torch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load, read, tiled


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--output',required=True);parser.add_argument('--core',type=int,default=192);args=parser.parse_args();model=load(args.checkpoint,'cuda' if torch.cuda.is_available() else 'cpu'); config=json.loads((ROOT/'config/experiment.json').read_text(encoding='utf-8-sig'));rows=[]
    with torch.inference_mode():
        for record in config['validation']['real_raw_inputs']:
            path=ROOT/record['path'];raw=read(path);x=torch.from_numpy(raw.astype(np.float32)/255)[None,None].to(next(model.parameters()).device);full=model(x);cut=tiled(model,x,core=args.core);difference=(full-cut).abs()*255;rows.append({'image':record['name'],'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mean_gray':float(difference.mean()),'max_gray':float(difference.max()),'p99_gray':float(torch.quantile(difference.flatten(),.99))})
    result={'schema_version':1,'status':'pass' if max(r['max_gray'] for r in rows)<.05 else 'blocked','checkpoint':str(Path(args.checkpoint).resolve()),'checkpoint_sha256':hashlib.sha256(Path(args.checkpoint).read_bytes()).hexdigest(),'core':args.core,'rows':rows,'meaning':'Direct/halo-tiled numerical parity only; it does not prove shape or motion quality.'};out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2));return 0 if result['status']=='pass' else 2


if __name__=='__main__':raise SystemExit(main())
