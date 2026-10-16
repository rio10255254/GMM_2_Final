"""Validate R109 data, forward pass, identity behavior, and tile parity."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[1];CONFIG=json.loads((ROOT/'config/experiment.json').read_text(encoding='utf-8'));sys.path.insert(0,str(ROOT/'model'));sys.path.insert(0,str(ROOT/'training'));from r109_model import build_model,count_parameters;from r109_dataset import R109Dataset
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
@torch.inference_mode()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',default='');args=parser.parse_args();manifest=ROOT/CONFIG['data']['package_root']/'manifest.json'
 if not manifest.exists() or sha(manifest)!=CONFIG['data']['source_manifest_sha256']:raise RuntimeError('Prepared data manifest invalid')
 payload=json.loads(manifest.read_text(encoding='utf-8'));counts={split:sum(row['split']==split for row in payload['records']) for split in ('train','validation')}
 if counts!={'train':5000,'validation':512}:raise RuntimeError(counts)
 device=torch.device('cuda:0' if torch.cuda.is_available() else 'cpu');model=build_model().to(device)
 if args.checkpoint:model.load_state_dict(torch.load(args.checkpoint,map_location=device,weights_only=False)['model'])
 model.eval();sample=R109Dataset('validation',epoch=1,limit=1)[0];source=sample['source'].to(device);output=model(source);finite=bool(torch.isfinite(output).all());identity_change=float(torch.abs(output[1]-source[1]).mean()*255)
 generator=torch.Generator(device=device).manual_seed(1093999);image=torch.rand((1,1,512,512),generator=generator,device=device);full=model(image);halo=192;core=128;padded=torch.nn.functional.pad(image,(halo,halo,halo,halo),mode='reflect');canvas=torch.zeros_like(image)
 for y in range(0,512,core):
  for x in range(0,512,core):value=model(padded[...,y:y+core+2*halo,x:x+core+2*halo]);canvas[...,y:y+core,x:x+core]=value[...,halo:halo+core,halo:halo+core]
 difference=torch.abs(full-canvas)*255;interior=difference[...,halo:-halo,halo:-halo];result={'status':'complete','checkpoint':args.checkpoint or None,'data_counts':counts,'manifest_sha256':sha(manifest),'parameters':count_parameters(model),'finite_output':finite,'identity_change_gray':identity_change,'tile_interior_mean_gray':float(interior.mean()),'tile_interior_p99_gray':float(torch.quantile(interior,.99)),'tile_interior_max_gray':float(interior.max()),'real_training_pixels':False,'scratch_only':True}
 if not finite:raise RuntimeError('Non-finite output')
 (ROOT/'validation/prepared_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
