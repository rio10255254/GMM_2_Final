"""Run unchanged scientific code with the separately tested, disclosed I/O adapter."""
import sys,argparse
from pathlib import Path
REC=Path(__file__).resolve().parent;ROOT=REC.parents[1]
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT))
import common
from robust_io import atomic,mutable_metadata,read_json_retry

def verify_recovery():
    manifest=common.load(REC/'recovery_manifest.json')
    for path,h in manifest['recovery_source_sha256'].items():
        if common.sha(path)!=h:raise RuntimeError('Recovery source changed')
    for item in manifest['required_records']:
        if common.sha(item['path'])!=item['sha256']:raise RuntimeError('Recovery evidence changed')
    return manifest

def main(arm,seed,resume):
    verify_recovery()
    # Imports copy this one operational function. All training/math/data/readout
    # functions and the original frozen identity checks remain unchanged.
    common.atomic=atomic
    original_load=common.load
    common.load=lambda path:read_json_retry(path) if mutable_metadata(path) else original_load(path)
    import train
    original_verify=train.verify_binding
    def complete_verify(binding):
        original_verify(binding);verify_recovery()
    train.verify_binding=complete_verify
    original_verify(common.load(ROOT/'config/frozen_training.json'))
    stamp=common.now().replace(':','').replace('.','_')
    common.save(REC/f'child_attempt_{arm}_{seed}_{stamp}.json',dict(arm=arm,seed=seed,resume=resume,adapter=common.record(REC/'recovery_manifest.json'),original_frozen_study=common.record(ROOT/'config/frozen_training.json'),changed_runtime_functions=['common.atomic and common.load retry only mutable execution metadata','train.verify_binding adds recovery identity validation'],model_loss_data_optimizer_readouts_unchanged=True))
    train.train(arm,seed,resume)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['I','P'],required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args();main(a.arm,a.seed,a.resume)
