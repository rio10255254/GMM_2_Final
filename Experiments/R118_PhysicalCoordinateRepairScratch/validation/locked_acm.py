"""Bridge R118 to the unchanged thesis ACM evaluator.

Historical evaluator paths are validation dependencies only. They are not
needed by the self-contained training or inference programs.
"""
from __future__ import annotations
import importlib.util
import json
import math
from pathlib import Path
import sys
import types
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load,tiled
R114=ROOT.parent/'R114_ConfidenceGatedRecoverableScratch'

def load_model(checkpoint,device):return load(checkpoint,device)
def canonical_tile_config(model,core=512,halo=None):
    return types.SimpleNamespace(core=core,halo=halo or model.minimum_halo_px,name='R118')
@torch.inference_mode()
def predict_canonical_tiled(model,image,config):
    output=tiled(model,image,config.core,config.halo)
    # Adapter-only legacy columns: R118 has no multiplicative correction gates.
    one=output.new_ones(1,1,1,1)
    return types.SimpleNamespace(output=output,maps={'width_gate':one,'shift_gate':one,'profile_visibility':one},
                                 tile_count=math.ceil(image.shape[-2]/config.core)*math.ceil(image.shape[-1]/config.core))
def main():
    adapter=types.ModuleType('validation.r114_split_profile_adapter')
    adapter.load_model=load_model;adapter.canonical_tile_config=canonical_tile_config;adapter.predict_canonical_tiled=predict_canonical_tiled
    sys.modules[adapter.__name__]=adapter
    path=R114/'validation/run_split_profile_locked_acm.py'
    spec=importlib.util.spec_from_file_location('r118_locked_runner',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    result=module.main()
    return result
if __name__=='__main__':raise SystemExit(main())
