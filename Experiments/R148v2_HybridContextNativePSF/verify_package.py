from __future__ import annotations
import argparse,torch
from utils import ROOT,load,sha,model_config,verify_bank_lock
FROZEN=('model.py','dataset.py','losses.py','train.py','training_policy.py','infer.py','utils.py','optical/fullres_psf.py','config/model.json','config/train.json','config/data.json','calibration/measured_psf_bank.npz','calibration/BANK_LOCK.json','data/PAYLOAD_LOCK.json','data/payload/manifest.json','data/geometry/manifest.json','scripts/prepare_geometry.py','scripts/preflight.py','scripts/launch_r148v2.py')
def verify_source_lock():
 lock=load(ROOT/'config/SOURCE_LOCK.json');assert set(lock['files'])==set(FROZEN)
 for p,h in lock['files'].items():
  if sha(ROOT/p)!=h:raise RuntimeError('Frozen source changed: '+p)
 return lock
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=('structural','infer-ready'),default='structural');a=p.parse_args();verify_source_lock();bank=verify_bank_lock();assert sha(ROOT/'data/payload/manifest.json')==load(ROOT/'data/PAYLOAD_LOCK.json')['manifest_sha256'];assert len(load(ROOT/'data/geometry/manifest.json')['entries'])==768;path=ROOT/'runs/formal_8192/checkpoints/step08192.pth';trained=path.exists()
 if trained:
  cp=torch.load(path,map_location='cpu',weights_only=False);assert cp['step']==8192 and cp['checkpoint_kind']=='trained_model' and cp['context_mode']=='hybrid' and cp['model_config']==model_config() and cp['psf_bank_sha256']==bank['bank_sha256']
 if a.mode=='infer-ready' and not trained:raise RuntimeError('Formal model incomplete')
 print(dict(package=model_config()['model_name'],frozen_files=len(FROZEN),parents=768,geometry=768,formal_complete=trained))
if __name__=='__main__':main()
