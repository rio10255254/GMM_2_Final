"""Preserve R140v2 backbone without claiming a trained adaptive selector."""
from __future__ import annotations
import argparse
from pathlib import Path
import torch
from utils import ROOT,model_config,setup,sha,now
from model import Model

SOURCE=Path(r'D:\GMM_2_Final\Experiments\R140v2_StableUNet\runs\formal_8192\checkpoints\step08192.pth')
EXPECTED='b96980287f02329b36f2188886462e51cadabad2259c8a13018f68e3b3f2650c'

def main():
    p=argparse.ArgumentParser();p.add_argument('--backbone-only',action='store_true');args=p.parse_args()
    if sha(SOURCE)!=EXPECTED:raise RuntimeError('R140v2 source checkpoint changed')
    cp=torch.load(SOURCE,map_location='cpu',weights_only=False)
    if cp['step']!=8192 or cp['model_name']!='R140v2-StableUNet':raise RuntimeError('Wrong source checkpoint')
    old={k:v for k,v in cp['model'].items() if not k.startswith('refiner.optics.')}
    output=ROOT/'weights'
    output.mkdir(exist_ok=True)
    if args.backbone_only:
        path=output/'backbone_seed_from_R140v2.pth'
        torch.save(dict(checkpoint_kind='backbone_seed_no_bank',source_checkpoint_sha256=EXPECTED,
                        backbone=old,model_config=model_config(),selector_trained=False,
                        no_real_psf100_present=True,created_utc=now()),path)
        print('BACKBONE_SEED_ONLY',len(old),'keys',sha(path));return
    cfg=model_config();bank=ROOT/cfg['psf_bank'];setup(1309001)
    model=Model(cfg,ROOT);state=model.state_dict()
    for name,value in old.items():
        if name not in state or state[name].shape!=value.shape:
            raise RuntimeError('Backbone architecture mismatch: '+name)
        state[name]=value
    state['refiner.optics.beta']=cp['model']['refiner.optics.beta']
    state['refiner.optics.beta_scale']=cp['model']['refiner.optics.beta_scale']
    model.load_state_dict(state,strict=True)
    path=output/'derived_from_R140v2.pth'
    torch.save(dict(checkpoint_kind='derived_selector_untrained',model_name=cfg['model_name'],
                    source_checkpoint_sha256=EXPECTED,model={k:v.cpu() for k,v in model.state_dict().items()},
                    model_config=cfg,bank_sha256=sha(bank),selector_trained=False,
                    selector_adaptivity_validated=False,backbone_tensors_copied=len(old),
                    created_utc=now()),path)
    print('DERIVED_OPERATIONAL_CHECKPOINT',len(old),'backbone tensors',sha(path))
if __name__=='__main__':main()
