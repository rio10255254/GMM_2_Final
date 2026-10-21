"""Validate subpixel translation equivariance for the completed R108B arms."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('r108b_core',ROOT/'scripts/run_microprobe.py')
if spec is None or spec.loader is None:raise RuntimeError('Cannot load R108B core')
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)
DEVICE=core.DEVICE


def warp(x,dx,dy):
    n,c,h,w=x.shape;theta=torch.zeros((n,2,3),device=x.device,dtype=x.dtype);theta[:,0,0]=1;theta[:,1,1]=1;theta[:,0,2]=-2*dx/max(w-1,1);theta[:,1,2]=-2*dy/max(h-1,1);grid=F.affine_grid(theta,x.shape,align_corners=True);return F.grid_sample(x,grid,mode='bilinear',padding_mode='reflection',align_corners=True)


@torch.inference_mode()
def apply(model,x,selector=None):
    details=model(x)
    return details.output if selector is None else (x+selector(x,details.proposal)*(details.proposal-x)).clamp(0,1)


def main():
    splits=core.prepare_data();data=core.tensor_data(splits['holdout']);source=data['source1'][:48]
    direct=core.ParallelExperts(False).to(DEVICE);direct.load_state_dict(torch.load(ROOT/'weights/direct_parallel.pth',map_location=DEVICE,weights_only=False)['model']);direct.eval()
    joint=core.ParallelExperts(True).to(DEVICE);joint.load_state_dict(torch.load(ROOT/'weights/joint_unsupervised_gate.pth',map_location=DEVICE,weights_only=False)['model']);joint.eval()
    selector=core.AdoptionSelector().to(DEVICE);selector.load_state_dict(torch.load(ROOT/'weights/staged_selector.pth',map_location=DEVICE,weights_only=False)['model']);selector.eval()
    rows={};dx,dy=.70,-.40;margin=32
    for name,model,select in [('direct_parallel',direct,None),('joint_unsupervised_gate',joint,None),('staged_outcome_selector',direct,selector)]:
        base=apply(model,source,select);shifted=apply(model,warp(source,dx,dy),select);expected=warp(base,dx,dy);delta=(shifted-expected).abs()[...,margin:-margin,margin:-margin]*255
        rows[name]={'dx_px':dx,'dy_px':dy,'images':len(source),'mean_abs_gray':float(delta.mean()),'p95_abs_gray':float(torch.quantile(delta,.95)),'p99_abs_gray':float(torch.quantile(delta,.99)),'max_abs_gray':float(delta.max())}
    result={'status':'complete','type':'subpixel_translation_equivariance','results':rows,'claim_boundary':'This tests local response consistency, not external-GMF accuracy or stage truth.'}
    (ROOT/'results/translation_response.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True);return 0


if __name__=='__main__':raise SystemExit(main())

