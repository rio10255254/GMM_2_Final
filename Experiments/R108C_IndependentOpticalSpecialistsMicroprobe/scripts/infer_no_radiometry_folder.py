"""Tiled folder inference for the frozen no-radiometry R108C guard-0.25 probe."""
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,sys
from pathlib import Path
import cv2,numpy as np,torch
import torch.nn.functional as F
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('nr_core',ROOT/'scripts/evaluate_no_radiometry.py');nr=importlib.util.module_from_spec(spec);sys.modules[spec.name]=nr;spec.loader.exec_module(nr);DEVICE=nr.DEVICE
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return cv2.imdecode(np.fromfile(str(path),np.uint8),cv2.IMREAD_GRAYSCALE).astype(np.float32)/255
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);cv2.imencode('.bmp',np.round(np.clip(value,0,1)*255).astype(np.uint8))[1].tofile(str(path))
@torch.inference_mode()
def pipeline(models,selectors,x):
 for name in nr.ORDER:
  proposal=nr.cal.adopt.expert_proposal(name,models[name],x);x=(x+selectors[name](x,proposal)*(proposal-x)).clamp(0,1)
 return x
@torch.inference_mode()
def tiled(models,selectors,image,core=256,halo=192):
 tensor=torch.from_numpy(image[None,None]).to(DEVICE);h,w=image.shape;padded=F.pad(tensor,(halo,halo,halo,halo),mode='reflect');out=torch.zeros_like(tensor)
 for y in range(0,h,core):
  for x in range(0,w,core):
   ch=min(core,h-y);cw=min(core,w-x);tile=padded[...,y:y+ch+2*halo,x:x+cw+2*halo];value=pipeline(models,selectors,tile);out[...,y:y+ch,x:x+cw]=value[...,halo:halo+ch,halo:halo+cw]
 return out[0,0].cpu().numpy()
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--guard',type=float,default=.25);args=p.parse_args();source=Path(args.input);output=Path(args.output);models,selectors=nr.load(float(args.guard));files=sorted(path for path in source.rglob('*') if path.is_file() and path.suffix.lower() in {'.bmp','.png','.tif','.tiff'});rows=[]
 for index,path in enumerate(files,1):destination=(output/path.relative_to(source)).with_suffix('.bmp');write(destination,tiled(models,selectors,read(path)));rows.append({'input':str(path),'input_sha256':sha(path),'output':str(destination),'output_sha256':sha(destination)});print(json.dumps({'done':index,'total':len(files)}),flush=True)
 with (output/'inference_manifest.csv').open('w',newline='',encoding='utf-8-sig') as handle:writer=csv.DictWriter(handle,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
 (output/'inference_state.json').write_text(json.dumps({'status':'complete','images':len(rows),'guard':float(args.guard),'radiometry':False,'tiled':True},indent=2),encoding='utf-8');return 0
if __name__=='__main__':raise SystemExit(main())

