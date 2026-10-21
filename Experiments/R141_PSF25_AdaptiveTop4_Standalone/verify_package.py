"""Verify local package integrity and distinguish structural from inference readiness."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,torch
from utils import ROOT,load,sha,model_config,train_config,verify_bank_lock
from model import Model

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['structural','infer-ready'],default='structural')
    p.add_argument('--checkpoint',help='Trained checkpoint to verify; default is package derived checkpoint')
    args=p.parse_args()
    record=load(ROOT/'config/INTEGRITY.json')
    checked=0
    for rel,expected in record['files'].items():
        file=ROOT/rel
        if not file.is_file() or sha(file)!=expected:raise RuntimeError('Package file missing or changed: '+rel)
        checked+=1
    cfg=model_config();train=train_config()
    if cfg['psf_count'] not in (25,100) or cfg['psf_topk']!=(4 if cfg['psf_count']==25 else 8):
        raise RuntimeError('Wrong PSF count/top-K pairing')
    entries=load(ROOT/'data/manifest.json')['entries']
    if len(entries)!=768 or len({x['parent_id'] for x in entries})!=768:
        raise RuntimeError('Synthetic training data incomplete')
    if train['updates']!=8192:raise RuntimeError('Training budget changed')
    weight_lock=load(ROOT/'weights/WEIGHT_LOCK.json')
    for rel,expected in weight_lock['files'].items():
        if sha(ROOT/rel)!=expected:raise RuntimeError('Starter weight file changed: '+rel)
    bank=ROOT/cfg['psf_bank']
    bank_present=bank.is_file()
    if cfg['psf_count']==25 and not bank_present:raise FileNotFoundError('25-PSF bank missing')
    bank_lock=None
    if bank_present:
        bank_lock=verify_bank_lock()
        with np.load(bank,allow_pickle=False) as z:
            a=z['all_kernels']
        if a.shape!=(cfg['psf_count'],101,101) or not np.isfinite(a).all() or (a<0).any() or (a.sum((1,2))<=0).any():
            raise ValueError('Installed PSF bank invalid')
        model=Model(cfg,ROOT).cpu().eval()
        model.refiner.optics.set_beta_scale(.28)
        with torch.inference_mode():
            out=model(torch.full((1,1,202,202),.5,dtype=torch.float32))
        if not torch.isfinite(out).all():raise FloatingPointError('Inference smoke returned nonfinite output')
        if int((model.refiner.optics.last_sparse_weights[0]>0).sum())!=cfg['psf_topk']:
            raise AssertionError('Top-K did not select exactly K')
    checkpoint=Path(args.checkpoint) if args.checkpoint else ROOT/'weights/derived_from_R140v2.pth'
    inference_ready=False;selector_proven=False
    if checkpoint.is_file() and bank_present:
        cp=torch.load(checkpoint,map_location='cpu',weights_only=False)
        if cp['bank_sha256']!=sha(bank) or cp['model_config']!=cfg:
            raise RuntimeError('Operational checkpoint does not match bank/config')
        model.load_state_dict(cp['model'],strict=True)
        inference_ready=cp['checkpoint_kind'] in ('derived_selector_untrained','trained_model') and not bank_lock.get('test_only',False)
        selector_proven=cp.get('selector_adaptivity_validated',False)
    if args.mode=='infer-ready' and not inference_ready:
        raise RuntimeError('Inference is not ready: real PSF bank and usable checkpoint are required')
    result=dict(package=cfg['model_name'],mode=args.mode,integrity_files_checked=checked,
                data_parents=768,bank_present=bank_present,bank_count=cfg['psf_count'] if bank_present else None,
                top_k=cfg['psf_topk'],inference_ready=inference_ready,
                adaptive_selector_validated_on_real_psfs=selector_proven,
                structural_ready=True)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
