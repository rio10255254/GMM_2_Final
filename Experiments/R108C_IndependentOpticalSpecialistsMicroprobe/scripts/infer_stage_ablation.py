"""Save every frozen R108C pipeline stage for R74 ACM ablation."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]


ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('inference_core',ROOT/'scripts/infer_calibrated.py')
if spec is None or spec.loader is None:raise RuntimeError('Cannot load inference core')
infer=importlib.util.module_from_spec(spec);sys.modules[spec.name]=infer;spec.loader.exec_module(infer)
SOURCE=Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/src'))
ORDER=infer.cal.adopt.ORDER


def main():
 models,selectors=infer.load_pipeline(.12);files=sorted(SOURCE.rglob('*.bmp'));roots={name:ROOT/f'results/stage_ablation/R74/{index+1:02d}_{name}' for index,name in enumerate(ORDER)}
 with torch.inference_mode():
  for file_index,path in enumerate(files,1):
   relative=path.relative_to(SOURCE);x=torch.from_numpy(infer.read_gray(path)[None,None]).to(infer.DEVICE)
   for name in ORDER:
    proposal=infer.cal.adopt.expert_proposal(name,models[name],x);alpha=selectors[name](x,proposal);x=(x+alpha*(proposal-x)).clamp(0,1);infer.write_gray((roots[name]/relative).with_suffix('.bmp'),x[0,0].cpu().numpy())
   print(json.dumps({'done':file_index,'total':len(files)}),flush=True)
 for name,root in roots.items():(root/'inference_state.json').write_text(json.dumps({'status':'complete','stage':name,'images':len(files),'guard':.12},indent=2),encoding='utf-8')
 return 0


if __name__=='__main__':raise SystemExit(main())

