"""Reconcile repair artifacts and create a truthful execution-readiness record."""
from pathlib import Path
import hashlib
import json
import platform
from datetime import datetime,timezone
import sys
import cv2
import numpy as np
import torch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from inference.run import load

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    checks=json.loads((ROOT/'validation/preflight.json').read_text())
    if checks['status']!='pass':raise RuntimeError('preflight not passed')
    chosen=ROOT/'runs/verified_physical_repair'
    state=json.loads((chosen/'SUMMARY.json').read_text())
    if state['status']!='complete' or state['epochs_completed']!=12:raise RuntimeError('final short run incomplete')
    weight=chosen/'weights/epoch_012.pth';model=load(weight)
    with torch.inference_mode():
        image=model(torch.ones(1,1,64,64)*.4)
    if not torch.isfinite(image).all():raise RuntimeError('checkpoint output failed')
    acm=json.loads((ROOT/'results/final_probe_acm/analysis_summary.json').read_text())
    sem=json.loads((ROOT/'results/final_probe_sem/summary.json').read_text())
    if acm['status']!='complete' or sem['status']!='complete':raise RuntimeError('external development checks incomplete')
    for suffix in ('real.png','sources.json'):
        if not (chosen/'previews'/f'epoch_012_{suffix}').exists():raise RuntimeError('missing verified real preview')
    config=json.loads((ROOT/'config/experiment.json').read_text())
    data=json.loads((ROOT/'data/package/manifest.json').read_text())
    sealed=json.loads((ROOT/'data/confirmation/manifest.json').read_text())
    if sealed['model_predictions_generated'] or sealed['count']!=144:raise RuntimeError('confirmation policy mismatch')
    comparison=json.loads((ROOT/'results/probe_comparison.json').read_text())
    parity=json.loads((ROOT/'validation/trained_tile_parity.json').read_text())
    if parity['status']!='pass':raise RuntimeError('trained model tiling is not verified')
    ready={'status':'repair_implemented_and_executed','engineering_checks_passed':True,
           'as_of_utc':datetime.now(timezone.utc).isoformat(),
           'formal_training_started':False,'formal_epochs_planned':config['training']['formal_epochs'],
           'model_promoted':False,'short_probe_is_not_final_model':True,
           'post_probe_packaging_changes':'Verified Raw files were copied byte-identically into this package; path resolution and configuration wiring were updated. Default schedule, numerical model and objectives are unchanged.',
           'data_counts':data['counts'],'sealed_confirmation_scenes':sealed['count'],
           'trained_tile_parity':parity,
           'scratch_checkpoint':str(weight.relative_to(ROOT)),'checkpoint_sha256':sha(weight),
           'runtime':{'python':platform.python_version(),'torch':torch.__version__,'cuda':torch.version.cuda},
           'r74':acm['results'][0]['effect'],'sem':sem,'paired_development_metrics':comparison['results']['final_physical_repair'],
           'known_limits':['Synthetic paired position dispersion still needs comparison with Raw and final real LSC.',
                           'Asymmetric-halo performance is tracked separately; aggregate gains do not erase family regressions.',
                           'Optical parameters are explicit priors; a uniquely identified microscope PSF is not claimed.'],
           'protected_R117_checkpoint_sha256':sha(ROOT.parent/'R117_CenterLockedSubpixelScratch/runs/r117_formal_scratch_20260905_004452/weights/epoch_042.pth')}
    ready['paired_development_metrics'].pop('rows',None)
    (ROOT/'READY.json').write_text(json.dumps(ready,indent=2,allow_nan=False),encoding='utf-8')
    index={}
    roles={'repair_smoke_all_stages':'early execution smoke',
           'paired_repair_with_detail':'early position normalization diagnostic',
           'repaired_position_with_detail':'matched detail arm before fine-reliability repair',
           'matched_without_detail':'matched no-detail control before fine-reliability repair',
           'final_repair_detail':'rejected alternative distance convention; historical name is not selection',
           'final_physical_repair':'interrupted reduction-repair diagnostic; never resumed',
           'verified_physical_repair':'final code short execution probe; not promoted model'}
    for directory in (ROOT/'runs').iterdir():
        if directory.is_dir():
            file=directory/'state.json'
            if file.exists():
                s=json.loads(file.read_text())
                index[directory.name]={'role':roles.get(directory.name,'other diagnostic'),'status':s['status'],'scratch':s.get('scratch')}
    (ROOT/'runs/RUN_INDEX.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
    code={str(p.relative_to(ROOT)):sha(p) for sub in ('model','training','inference','data','tests','scripts','validation')
          for p in (ROOT/sub).glob('*.py')}
    (ROOT/'reports/CODE_MANIFEST.json').write_text(json.dumps(code,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in ready.items() if k not in ('r74','paired_development_metrics')},indent=2))
if __name__=='__main__':main()
