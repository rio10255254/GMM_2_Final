"""Frozen tiled reconstruction of R73, R74, SEM and representative real images."""
from __future__ import annotations
import argparse,csv,hashlib,importlib.util,json,sys
from pathlib import Path
import cv2,numpy as np,pandas as pd,torch
import torch.nn.functional as F
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'model'));from r109_model import build_model
PROJECT_ROOT = Path(__file__).resolve().parents[3]
HELPER=Path(str(PROJECT_ROOT / 'Experiments/R96_LocalizedEvidenceProtectedScratch/scripts/evaluate_real_holdout.py'));SOURCES={'R73':Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/src')),'R74':Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/src')),'SEM':Path(str(PROJECT_ROOT / 'Experiments/R69_ACMContourSEMValidation/inputs/sem_paired_50x_exposure_stack'))};REAL=[Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation/5x_dense_raw.bmp')),Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation/20x_mixed_raw.bmp')),Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation/50x_array_raw.bmp')),Path(str(PROJECT_ROOT / 'Experiments/R100_CausalOperatorScratch/data/live_validation/pillar_center9_50x_raw.bmp'))]
def load(name,path):spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
helper=load('r109_locked_appearance',HELPER)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return helper.read_gray(path).astype(np.float32)/255
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);cv2.imencode('.bmp',np.round(np.clip(value,0,1)*255).astype(np.uint8))[1].tofile(str(path))
@torch.inference_mode()
def tiled(model,image,device,core=512,halo=192):
 tensor=torch.from_numpy(image[None,None]).to(device);h,w=image.shape;padded=F.pad(tensor,(halo,halo,halo,halo),mode='reflect');output=torch.zeros_like(tensor)
 for y in range(0,h,core):
  for x in range(0,w,core):ch,cw=min(core,h-y),min(core,w-x);tile=padded[...,y:y+ch+2*halo,x:x+cw+2*halo];value=model(tile);output[...,y:y+ch,x:x+cw]=value[...,halo:halo+ch,halo:halo+cw]
 return output[0,0].cpu().numpy()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--tag',required=True);args=parser.parse_args();checkpoint=Path(args.checkpoint);device=torch.device('cuda:0');model=build_model().to(device);model.load_state_dict(torch.load(checkpoint,map_location=device,weights_only=False)['model']);model.eval();output=ROOT/'results/posttraining'/args.tag;counts={};manifests=[]
 for suite,source in SOURCES.items():
  files=sorted(source.rglob('*.bmp'))
  for index,path in enumerate(files,1):destination=output/suite/path.relative_to(source);write(destination,tiled(model,read(path),device));manifests.append({'suite':suite,'input':str(path),'input_sha256':sha(path),'output':str(destination),'output_sha256':sha(destination)});print(json.dumps({'suite':suite,'done':index,'total':len(files)}),flush=True) if index%20==0 or index==len(files) else None
  counts[suite]=len(files)
 pd.DataFrame(manifests).to_csv(output/'reconstruction_manifest.csv',index=False)
 rows=[];previews=[]
 for path in REAL:
  raw=helper.read_gray(path);value=np.round(tiled(model,raw.astype(np.float32)/255,device)*255).astype(np.uint8);write(output/'real'/path.name,value.astype(np.float32)/255);rows.append({'image':path.name,**helper.appearance_metrics(raw,value,512)});small=[cv2.resize(image,(480,360),interpolation=cv2.INTER_AREA) for image in (raw,value,np.clip(np.abs(value.astype(np.int16)-raw.astype(np.int16))*8,0,255).astype(np.uint8))];previews.append(np.concatenate(small,1))
 frame=pd.DataFrame(rows);frame.to_csv(output/'real_appearance.csv',index=False);cv2.imencode('.png',np.concatenate(previews,0))[1].tofile(str(output/'real_raw_output_diff.png'));state={'status':'complete','tag':args.tag,'checkpoint':str(checkpoint),'checkpoint_sha256':sha(checkpoint),'counts':counts,'tiled':{'core':512,'halo':192},'real_median':{key:float(frame[key].median()) for key in frame.columns if key!='image'}};(output/'state.json').write_text(json.dumps(state,indent=2),encoding='utf-8');print(json.dumps(state),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
