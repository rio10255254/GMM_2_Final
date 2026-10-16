"""Causal probe for spatially smooth optical parameter fields on SEM."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results" / "sem_parameter_smoothing_sigma1"
CORE_PATH = ROOT / "scripts" / "run_probe.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


core = load_module("r108g_parameter_smoothing_core", CORE_PATH)


@torch.inference_mode()
def forward_smooth(model, smoother, x: torch.Tensor):
    cues, blurred, magnitude, local_scale = model.cues(x)
    detector = model.detector_tower(F.silu(model.detector_stem(cues)))
    renderer = model.renderer_tower(F.silu(model.renderer_stem(cues)))
    boundary = torch.sigmoid(model.boundary_head(detector)); necessity = torch.sigmoid(model.necessity_head(detector))
    source_support = ((magnitude / (local_scale + 2 / 255) - 0.05) / 1.10).clamp(0, 1)
    support = torch.maximum(source_support, 0.85 * F.max_pool2d(boundary, 9, 1, 4)).clamp(0, 1); effective = necessity * support
    smooth_gx, smooth_gy = core.dcore.gradients(blurred[1]); smooth_magnitude = torch.sqrt(smooth_gx.square() + smooth_gy.square() + 1e-8)
    normal_x, normal_y = smooth_gx / smooth_magnitude, smooth_gy / smooth_magnitude
    raw_shift = 1.5 * torch.tanh(model.flow_head(renderer)); raw_gain = 1.0 + 2.5 * torch.sigmoid(model.coefficient_head(renderer))
    normal_shift = smoother(raw_shift); width_gain = smoother(raw_gain)
    flow = torch.cat([normal_shift * normal_x, normal_shift * normal_y], dim=1); warped = model.warp(x, flow * effective)
    local_max = F.max_pool2d(warped, 21, 1, 10); local_min = -F.max_pool2d(-warped, 21, 1, 10); dynamic = (local_max - local_min).clamp_min(2 / 255)
    unit = ((warped - local_min) / dynamic).clamp(1e-3, 1 - 1e-3); corrected = torch.sigmoid(width_gain * (torch.log(unit) - torch.log1p(-unit)))
    proposal = local_min + dynamic * corrected; output = (x + effective * (proposal - x)).clamp(0, 1)
    def tv(value): return float((torch.abs(value[...,1:]-value[...,:-1]).mean()+torch.abs(value[...,1:,:]-value[...,:-1,:]).mean()).detach())
    return output, {"raw_shift_tv": tv(raw_shift), "smooth_shift_tv": tv(normal_shift), "raw_gain_tv": tv(raw_gain), "smooth_gain_tv": tv(width_gain)}


@torch.inference_mode()
def tiled(model, smoother, image: np.ndarray, core_size: int = 256, halo: int = 192):
    tensor=torch.from_numpy(image[None,None]).to(core.DEVICE);height,width=image.shape;padded=F.pad(tensor,(halo,halo,halo,halo),mode='reflect');output=torch.zeros_like(tensor);stats=[]
    for y in range(0,height,core_size):
        for x in range(0,width,core_size):
            crop_h,crop_w=min(core_size,height-y),min(core_size,width-x);tile=padded[...,y:y+crop_h+2*halo,x:x+crop_w+2*halo];value,row=forward_smooth(model,smoother,tile);output[...,y:y+crop_h,x:x+crop_w]=value[...,halo:halo+crop_h,halo:halo+crop_w];stats.append(row)
    return output[0,0].cpu().numpy(),{key:float(np.mean([row[key] for row in stats])) for key in stats[0]}


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True);model=core.MidpointWidthOperator().to(core.DEVICE);checkpoint=core.WEIGHTS/'midpoint_width_operator.pth';model.load_state_dict(torch.load(checkpoint,map_location=core.DEVICE,weights_only=False)['model']);model.eval();smoother=core.dcore.Blur(1.0).to(core.DEVICE).eval();rows=[]
    for path in sorted(core.ecore.SEM_ROOT.glob('*.bmp')):
        raw=core.dcore.read_gray(path);value,stats=tiled(model,smoother,raw);core.dcore.write_gray(OUTPUT/path.name,value);rows.append({'exposure':int(path.stem),'change_gray':float(np.mean(np.abs(value-raw))*255),**stats})
    table=pd.DataFrame(rows);table.to_csv(OUTPUT/'action_summary.csv',index=False);summary={'status':'complete','sigma':1.0,'exposures':12,'median':{key:float(table[key].median()) for key in table.columns if key!='exposure'}};(OUTPUT/'state.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True);return 0
if __name__=='__main__':raise SystemExit(main())
