"""R109 single-image or folder inference with core-only tiling."""
from __future__ import annotations
import argparse,csv,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np,torch
import torch.nn.functional as F
ROOT=Path(__file__).resolve().parents[1];CONFIG=json.loads((ROOT/'config/experiment.json').read_text(encoding='utf-8'));sys.path.insert(0,str(ROOT/'model'));from r109_model import build_model
def read(path):
 value=cv2.imdecode(np.fromfile(str(path),np.uint8),cv2.IMREAD_GRAYSCALE)
 if value is None:raise RuntimeError(path)
 return value.astype(np.float32)/255
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);cv2.imencode('.bmp',np.round(np.clip(value,0,1)*255).astype(np.uint8))[1].tofile(str(path))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
@torch.inference_mode()
def tiled(model,image,device,core,halo):
 tensor=torch.from_numpy(image[None,None]).to(device);h,w=image.shape;padded=F.pad(tensor,(halo,halo,halo,halo),mode='reflect');output=torch.zeros_like(tensor)
 for y in range(0,h,core):
  for x in range(0,w,core):
   ch,cw=min(core,h-y),min(core,w-x);tile=padded[...,y:y+ch+2*halo,x:x+cw+2*halo];value=model(tile);output[...,y:y+ch,x:x+cw]=value[...,halo:halo+ch,halo:halo+cw]
 return output[0,0].cpu().numpy()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);parser.add_argument('--device',default='cuda:0');parser.add_argument('--core',type=int,default=int(CONFIG['inference']['core_size']));parser.add_argument('--halo',type=int,default=int(CONFIG['inference']['halo']));args=parser.parse_args();checkpoint=Path(args.checkpoint);payload=torch.load(checkpoint,map_location=args.device,weights_only=False);model=build_model().to(args.device);model.load_state_dict(payload['model']);model.eval();source=Path(args.input);files=[source] if source.is_file() else sorted(path for path in source.rglob('*') if path.is_file() and path.suffix.lower() in {'.bmp','.png','.tif','.tiff'});output=Path(args.output);rows=[]
 for index,path in enumerate(files,1):destination=(output/path.name) if source.is_file() else (output/path.relative_to(source)).with_suffix('.bmp');write(destination,tiled(model,read(path),torch.device(args.device),args.core,args.halo));rows.append({'input':str(path),'input_sha256':sha(path),'output':str(destination),'output_sha256':sha(destination)});print(json.dumps({'done':index,'total':len(files)}),flush=True)
 with (output/'inference_manifest.csv').open('w',newline='',encoding='utf-8-sig') as handle:writer=csv.DictWriter(handle,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
 (output/'inference_state.json').write_text(json.dumps({'status':'complete','images':len(rows),'checkpoint':str(checkpoint),'checkpoint_sha256':sha(checkpoint),'core':args.core,'halo':args.halo},indent=2),encoding='utf-8');return 0
if __name__=='__main__':raise SystemExit(main())
