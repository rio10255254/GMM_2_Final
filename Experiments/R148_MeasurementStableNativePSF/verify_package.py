from __future__ import annotations
import argparse,torch
from utils import ROOT,load,sha,model_config,verify_bank_lock
FROZEN=('model.py','dataset.py','losses.py','train.py','training_policy.py','infer.py','utils.py','optical/fullres_psf.py','config/model.json','config/train.json','config/data.json','calibration/measured_psf_bank.npz','calibration/BANK_LOCK.json','data/BASE_DATA_LOCK.json','data/payload/manifest.json','scripts/prepare_data.py','scripts/preflight.py','scripts/launch_r148.py')
def verify_source_lock():
 lock=load(ROOT/'config/SOURCE_LOCK.json');assert set(lock['files'])==set(FROZEN)
 for p,h in lock['files'].items():
  if sha(ROOT/p)!=h:raise RuntimeError('Frozen source changed: '+p)
 return lock
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=('structural','infer-ready'),default='structural');a=p.parse_args();verify_source_lock();bank=verify_bank_lock();manifest=load(ROOT/'data/payload/manifest.json');assert len(manifest['entries'])==768
 path=ROOT/'runs/formal_8192/checkpoints/step08192.pth';trained=path.is_file()
 if trained:
  cp=torch.load(path,map_location='cpu',weights_only=False);assert cp['step']==8192 and cp['checkpoint_kind']=='trained_model' and cp['model_config']==model_config() and cp['data_manifest_sha256']==sha(ROOT/'data/payload/manifest.json') and cp['psf_bank_sha256']==bank['bank_sha256']
 if a.mode=='infer-ready' and not trained:raise RuntimeError('Formal checkpoint not complete')
 print(dict(package=model_config()['model_name'],frozen_files=len(FROZEN),parents=len(manifest['entries']),bank_count=bank['count'],formal_complete=trained))
if __name__=='__main__':main()
