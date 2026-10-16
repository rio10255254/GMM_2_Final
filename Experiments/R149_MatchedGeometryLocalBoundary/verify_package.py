from __future__ import annotations
import argparse,torch
from utils import ROOT,load,sha,model_config,verify_bank_lock,verify_data_lock
FROZEN=('model.py','dataset.py','losses.py','train.py','training_policy.py','infer.py','utils.py','verify_package.py','optical/fullres_psf.py','config/model.json','config/train.json','config/data.json','calibration/measured_psf_bank.npz','calibration/BANK_LOCK.json','data/manifest.json','data/DATA_LOCK.json','scripts/prepare_matched_data.py','scripts/preflight.py','scripts/launch_r149.py')
def verify_source_lock():
 lock=load(ROOT/'config/SOURCE_LOCK.json');assert set(lock['files'])==set(FROZEN)
 for p,h in lock['files'].items():
  if sha(ROOT/p)!=h:raise RuntimeError('Frozen source changed: '+p)
 return lock
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=('structural','infer-ready'),default='structural');a=p.parse_args();verify_source_lock();bank=verify_bank_lock();data=verify_data_lock();manifest=load(ROOT/'data/manifest.json');assert len(manifest['entries'])==768 and data['overlay_entries']==96;path=ROOT/'runs/formal_8192/checkpoints/step08192.pth';trained=path.exists()
 if trained:
  cp=torch.load(path,map_location='cpu',weights_only=False);assert cp['step']==8192 and cp['checkpoint_kind']=='trained_model' and cp['context_mode']=='hybrid' and cp['loss_mode']=='local' and cp['model_config']==model_config() and cp['psf_bank_sha256']==bank['bank_sha256'] and cp['data_manifest_sha256']==data['manifest_sha256']
 if a.mode=='infer-ready' and not trained:raise RuntimeError('Formal model incomplete')
 print(dict(package=model_config()['model_name'],frozen_files=len(FROZEN),parents=768,overlay_parents=data['overlay_entries'],formal_complete=trained))
if __name__=='__main__':main()
