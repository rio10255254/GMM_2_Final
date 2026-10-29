"""Frozen R73/R74 inference for the sigma-1 parameter smoothing probe."""
from __future__ import annotations
import importlib.util,json,sys
from pathlib import Path
import pandas as pd,torch
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROOT=Path(__file__).resolve().parents[1];MODULE=ROOT/'scripts/infer_sem_parameter_smoothing.py';OUTPUT=ROOT/'results/parameter_smoothing_sigma1'
SOURCES={'R73':Path(str(PROJECT_ROOT / 'Experiments/R73_R61ExpandedSyntheticACMGeneralization/data/r73_synthetic_acm_val/src')),'R74':Path(str(PROJECT_ROOT / 'Experiments/R74_R61HardMicroscopyACMGeneralization/data/r74_hard_acm_val/src'))}
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
smooth=load('r108g_external_smooth_core',MODULE);core=smooth.core
def main():
 model=core.MidpointWidthOperator().to(core.DEVICE);model.load_state_dict(torch.load(core.WEIGHTS/'midpoint_width_operator.pth',map_location=core.DEVICE,weights_only=False)['model']);model.eval();smoother=core.dcore.Blur(1.0).to(core.DEVICE).eval();counts={}
 for suite,source in SOURCES.items():
  rows=[];files=sorted(source.rglob('*.bmp'))
  for index,path in enumerate(files,1):
   value,_=smooth.tiled(model,smoother,core.dcore.read_gray(path));destination=OUTPUT/suite/path.relative_to(source);core.dcore.write_gray(destination,value);rows.append({'input':str(path),'output':str(destination)});print(json.dumps({'suite':suite,'done':index,'total':len(files)}),flush=True) if index%20==0 or index==len(files) else None
  pd.DataFrame(rows).to_csv(OUTPUT/f'{suite}_manifest.csv',index=False);counts[suite]=len(rows)
 (OUTPUT/'state.json').write_text(json.dumps({'status':'complete','sigma':1.0,'counts':counts},indent=2),encoding='utf-8');return 0
if __name__=='__main__':raise SystemExit(main())
