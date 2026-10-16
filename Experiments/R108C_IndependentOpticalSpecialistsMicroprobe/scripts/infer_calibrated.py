"""Inference for the frozen R108C guard-0.25 research probe."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch


ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('calibration_core',ROOT/'scripts/calibrate_denoise_adoption.py')
if spec is None or spec.loader is None:raise RuntimeError('Cannot load R108C calibration core')
cal=importlib.util.module_from_spec(spec);sys.modules[spec.name]=cal;spec.loader.exec_module(cal)
DEVICE=cal.DEVICE


def sha256(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def read_gray(path:Path)->np.ndarray:
 image=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
 if image is None:raise RuntimeError(path)
 return image.astype(np.float32)/255
def write_gray(path:Path,image:np.ndarray):path.parent.mkdir(parents=True,exist_ok=True);cv2.imencode('.bmp',np.round(np.clip(image,0,1)*255).astype(np.uint8))[1].tofile(str(path))


def load_pipeline(denoise_calibration:float):
 models=cal.adopt.load_models();selectors={name:cal.load_selector(name) for name in cal.adopt.ORDER};denoise=cal.adopt.AdoptionNet().to(DEVICE);denoise.load_state_dict(torch.load(ROOT/f'weights/adoption_denoise_calibrated_{denoise_calibration:.2f}.pth',map_location=DEVICE,weights_only=False)['model']);denoise.eval();selectors['denoise']=denoise
 for selector in selectors.values():
  selector.eval()
  for parameter in selector.parameters():parameter.requires_grad_(False)
 return models,selectors


@torch.inference_mode()
def infer(models,selectors,image:np.ndarray,tiled:bool)->np.ndarray:
 if tiled:return cal.adopt.tiled_pipeline(models,selectors,image,core_size=256,halo=192)
 tensor=torch.from_numpy(image[None,None]).to(DEVICE);return cal.adopt.pipeline(models,selectors,tensor)[0,0].cpu().numpy()


def main():
 parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);parser.add_argument('--tiled',action='store_true');parser.add_argument('--denoise-calibration',type=float,default=.25);args=parser.parse_args();source=Path(args.input);output=Path(args.output);files=sorted(path for path in source.rglob('*') if path.is_file() and path.suffix.lower() in {'.bmp','.png','.tif','.tiff'});models,selectors=load_pipeline(float(args.denoise_calibration));rows=[]
 for index,path in enumerate(files,1):
  relative=path.relative_to(source);destination=(output/relative).with_suffix('.bmp');value=infer(models,selectors,read_gray(path),bool(args.tiled));write_gray(destination,value);rows.append({'input':str(path),'input_sha256':sha256(path),'output':str(destination),'output_sha256':sha256(destination)});print(json.dumps({'done':index,'total':len(files),'file':relative.as_posix()}),flush=True)
 output.mkdir(parents=True,exist_ok=True)
 with (output/'inference_manifest.csv').open('w',newline='',encoding='utf-8-sig') as handle:writer=csv.DictWriter(handle,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
 summary={'status':'complete','input':str(source),'output':str(output),'images':len(rows),'tiled':bool(args.tiled),'denoise_calibration':float(args.denoise_calibration),'old_model_weights_used':False};(output/'inference_state.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())
