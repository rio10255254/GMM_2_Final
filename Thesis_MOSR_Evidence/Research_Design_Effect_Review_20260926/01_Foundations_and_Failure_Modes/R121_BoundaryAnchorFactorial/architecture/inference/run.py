"""Single-image or folder reconstruction; all paths are relative to this package."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
import cv2
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from model.network import build_model

@torch.inference_mode()
def tiled(model,x,core=512,halo=None):
    halo=model.minimum_halo_px if halo is None else halo
    if halo<model.minimum_halo_px:raise ValueError('insufficient halo')
    h,w=x.shape[-2:];out=torch.empty_like(x,dtype=torch.float32)
    for y in range(0,h,core):
        for xx in range(0,w,core):
            y1,x1=min(y+core,h),min(xx+core,w)
            sy,sx=max(0,y-halo),max(0,xx-halo);ey,ex=min(h,y1+halo),min(w,x1+halo)
            value=model(x[...,sy:ey,sx:ex])
            out[...,y:y1,xx:x1]=value[...,y-sy:y1-sy,xx-sx:x1-sx]
    if not torch.isfinite(out).all():raise FloatingPointError('nonfinite tiled output')
    return out

def load(checkpoint,device='cpu'):
    saved=torch.load(checkpoint,map_location='cpu',weights_only=False)
    if saved.get('scratch') is not True or saved.get('checkpoint_loaded') is not False:raise ValueError('invalid provenance')
    model=build_model(saved['model_config']);model.load_state_dict(saved['model'],strict=True)
    model.detail_enabled=saved.get('detail_enabled',True)
    return model.to(device).eval().requires_grad_(False)

def read(path):
    a=cv2.imdecode(np.fromfile(str(path),np.uint8),0)
    if a is None:raise ValueError(path)
    return a

def write(path,array):
    path.parent.mkdir(parents=True,exist_ok=True);ok,b=cv2.imencode(path.suffix,array)
    if not ok:raise ValueError(path)
    b.tofile(str(path))

def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--core',type=int,default=512);args=p.parse_args()
    source=Path(args.input);out=Path(args.output);device='cuda' if torch.cuda.is_available() else 'cpu'
    model=load(args.checkpoint,device)
    files=[source] if source.is_file() else sorted(x for x in source.iterdir() if x.suffix.lower() in ('.bmp','.png','.tif','.tiff'))
    if not files:raise ValueError('no images')
    records=[]
    for f in files:
        raw=read(f);x=torch.tensor(raw.astype(np.float32)/255)[None,None].to(device)
        result=tiled(model,x,args.core)[0,0].cpu().numpy()
        target=out/f.name
        if target.resolve()==f.resolve() or target.exists():raise FileExistsError('refuse to replace input or existing output')
        write(target,np.rint(np.clip(result,0,1)*255).astype(np.uint8))
        records.append({'source':str(f.resolve()),'source_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'output':str(target.resolve())})
    (out/'inference_manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
if __name__=='__main__':main()
