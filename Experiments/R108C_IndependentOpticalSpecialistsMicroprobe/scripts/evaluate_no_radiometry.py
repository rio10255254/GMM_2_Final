"""Evaluate the frozen guard-0.12 pipeline with radiometry disabled."""
from __future__ import annotations
import argparse,importlib.util,json,sys
from pathlib import Path
import cv2,numpy as np,torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cal_core',ROOT/'scripts/calibrate_denoise_adoption.py');cal=importlib.util.module_from_spec(spec);sys.modules[spec.name]=cal;spec.loader.exec_module(cal);DEVICE=cal.DEVICE;ORDER=['denoise','edge','texture']
def load(guard):
 models=cal.adopt.load_models();selectors={name:cal.load_selector(name) for name in cal.adopt.ORDER};d=cal.adopt.AdoptionNet().to(DEVICE);d.load_state_dict(torch.load(ROOT/f'weights/adoption_denoise_calibrated_{guard:.2f}.pth',map_location=DEVICE,weights_only=False)['model']);d.eval();selectors['denoise']=d;return models,selectors
@torch.inference_mode()
def pipeline(models,selectors,x):
 for name in ORDER:
  proposal=cal.adopt.expert_proposal(name,models[name],x);x=(x+selectors[name](x,proposal)*(proposal-x)).clamp(0,1)
 return x
def read(path):return cv2.imdecode(np.fromfile(str(path),np.uint8),cv2.IMREAD_GRAYSCALE).astype(np.float32)/255
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);cv2.imencode('.bmp',np.round(np.clip(value,0,1)*255).astype(np.uint8))[1].tofile(str(path))
@torch.inference_mode()
def reconstruct_folder(models,selectors,source,output):
 files=sorted(Path(source).rglob('*.bmp'))
 for index,path in enumerate(files,1):value=pipeline(models,selectors,torch.from_numpy(read(path)[None,None]).to(DEVICE))[0,0].cpu().numpy();write((Path(output)/path.relative_to(source)).with_suffix('.bmp'),value);print(json.dumps({'suite':Path(output).name,'done':index,'total':len(files)}),flush=True)
@torch.inference_mode()
def metrics(models,selectors):
 splits=cal.adopt.core.prepare_specialist_data();keys=['target','edge','mixed_input'];results={}
 for split,data in splits.items():
  t=cal.adopt.core.to_tensors(data,keys);out=pipeline(models,selectors,t['mixed_input']);results[split]=cal.adopt.final_metrics(t['mixed_input'],out,t['target'],t['edge'],t['role'])
 real=[]
 for path in cal.adopt.core.REAL_IMAGES:
  raw=read(path);value=pipeline(models,selectors,torch.from_numpy(raw[None,None]).to(DEVICE))[0,0].cpu().numpy();gx=cv2.Sobel(raw,cv2.CV_32F,1,0,ksize=3);gy=cv2.Sobel(raw,cv2.CV_32F,0,1,ksize=3);gm=np.hypot(gx,gy);support=gm>=np.quantile(gm,.9);gx2=cv2.Sobel(value,cv2.CV_32F,1,0,ksize=3);gy2=cv2.Sobel(value,cv2.CV_32F,0,1,ksize=3);real.append({'change_gray':float(np.mean(np.abs(value-raw))*255),'edge_gain':float(np.hypot(gx2,gy2)[support].mean()/gm[support].mean()),'fine_detail_ratio':float(np.mean(np.abs(value-cal.adopt.core.gaussian(value,1)))/np.mean(np.abs(raw-cal.adopt.core.gaussian(raw,1))))})
 results['real']={key:float(np.median([row[key] for row in real])) for key in real[0]};return results
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--guard',type=float,default=.12);args=parser.parse_args();guard=float(args.guard);tag=f'{guard:.2f}'.replace('.','p');models,selectors=load(guard);r73=Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/src'));r74=Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/src'));suffix='' if abs(guard-.12)<1e-9 else f'_g{tag}';reconstruct_folder(models,selectors,r73,ROOT/f'results/external_reconstruction/R73_no_radiometry{suffix}');reconstruct_folder(models,selectors,r74,ROOT/f'results/external_reconstruction/R74_no_radiometry{suffix}');result={'status':'complete','guard':guard,'disabled':['radiometry'],'order':ORDER,'metrics':metrics(models,selectors)};(ROOT/f'results/no_radiometry{suffix}_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
