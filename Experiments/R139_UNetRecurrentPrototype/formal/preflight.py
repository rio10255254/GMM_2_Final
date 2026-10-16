"""Run final read-only checks before creating the R139 formal training record."""
import ast,json,sys
from pathlib import Path
import torch,numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from utils import ROOT,load,save,sha,verify_frozen,verify_protected,verify_evaluation,now,config,model_config

def main():
 cfg=config();mc=model_config();lock=load(ROOT/'config/FORMAL_SOURCE_LOCK.json')
 verify_frozen(lock);verify_protected();verify_evaluation()
 ref=ROOT.parent/'R130_Clean';old=load(ref/'config_r130_clean.yaml')
 for field in ['model_seed','order_seed','noise_seed','splits','updates','epochs','warmup','save_every','dev_every','optimizer','loss','precision','tf32','deterministic']:
  assert cfg[field]==old[field],field
 assert cfg['train_crop']==old['training_crop'] and cfg['supervised_core']==old['supervised_core']
 assert sha(ROOT/'dataset.py')==sha(ref/'dataset_r130_clean.py')
 assert sha(ROOT/'losses.py')==sha(ref/'losses_r130_clean.py')
 assert sha(ROOT/'config/measured_psf_bank.npz')==sha(ROOT.parent/'R138_V42PSF8/calibration/measured_psf_bank.npz')
 for report in ['preflight.json','generated_pair_preflight.json','full_size_preflight.json']:
  assert (ROOT/'results'/report).is_file()
 assert load(ROOT/'results/preflight.json')['status']=='untrained_prototype_preflight_only'
 assert load(ROOT/'results/full_size_preflight.json')['exact_initial_identity']
 assert load(ROOT/'results/generated_pair_preflight.json')['trained_checkpoint_created'] is False
 assert torch.cuda.is_available()
 free,total=torch.cuda.mem_get_info();need=load(ROOT/'results/full_size_preflight.json')['peak_gpu_allocated_bytes']
 assert free>max(need*2,8*2**30),'Insufficient free GPU memory for formal launch'
 result=dict(ready_for_formal_training=True,checked_utc=now(),device=torch.cuda.get_device_name(),gpu_free_bytes=free,shared_synthetic_manifest_sha256=sha(ROOT/'data/manifest.json'),same_conditions_fields=['model_seed','order_seed','noise_seed','splits','updates','epochs','warmup','save_every','dev_every','optimizer','loss','precision','tf32','deterministic','train_crop','supervised_core'],intentional_differences=['U-Net architecture','V42-like half-resolution decoder PSF inserted once at final refinement','staged PSF activation and projected beta'],evaluation_inputs_unchanged=True,original_models_unchanged=True,formal_updates_before_this_check=0)
 save(ROOT/'results/formal_preflight.json',result);print('FORMAL_PREFLIGHT_PASS',json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
