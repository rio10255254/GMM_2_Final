"""Freeze after real executed readiness checks, before the first full update."""
import sys,platform,shutil
from common import *
sys.path.insert(0,str(ROOT))
import torch

def main():
    cfg=load(ROOT/'config/study.json')
    records=[ROOT/'results'/name for name in ['data_audit.json','engineering_preflight.json','real_evaluator_preflight.json','nonneutral_integration.json','training_data_consumer_preflight.json']]
    for p in records:
        if not load(p)['passed']:raise ValueError(f'Readiness did not pass: {p}')
    # Current functions must be the ones actually exercised, not new content
    # placed under the same filenames after the tests.
    engineering=load(ROOT/'results/engineering_preflight.json')
    tested=load(engineering['source_identity']['path'])
    current_executed=[ROOT/'model/network.py',ROOT/'model/observation.py',ROOT/'training/engine.py',ROOT/'training/data.py',ROOT/'training/objectives.py']
    for p in current_executed:
        if tested[str(p)]!=sha(p):raise RuntimeError(f'Code changed after engineering test: {p}')
    for filename,key in [('real_evaluator_preflight.json','sources'),('nonneutral_integration.json','source_sha256'),('training_data_consumer_preflight.json','source_sha256')]:
        for p,h in load(ROOT/'results'/filename)[key].items():
            if sha(p)!=h:raise RuntimeError('Tested implementation identity changed')
    protected=load(ROOT/'config/protected_before.json')
    changed=[p for p,h in protected.items() if not Path(p).is_file() or sha(p)!=h]
    if changed:raise RuntimeError(f'Historical evidence changed; no rebasing permitted: {changed[:10]}')
    save(ROOT/'results/historical_integrity_before_training.json',dict(passed=True,protected_files=len(protected),changed=[],utc=now()))
    # Static source compilation verifies the actual coordinator/trainer entry
    # points, in addition to the separately executed numerical and data paths.
    sources=[p for folder in ['model','training','evaluation','scripts','data'] for p in (ROOT/folder).glob('*.py')]
    for p in sources:compile(p.read_text(encoding='utf-8'),str(p),'exec')
    sources += [R125/'data/generator_v2.py',R124/'inference/tiling.py',*[R127/'scripts'/f'motion_reader{s}.py' for s in ['', '_v2','_v3']]]
    records += [ROOT/'config/study.json',ROOT/'config/initial_states.json',ROOT/'data/package/manifest.json',ROOT/'data/package/plan.json',ROOT/'results/real_baseline/verification.json',ROOT/'results/historical_integrity_before_training.json',R125/'results/real_panel_v2/frozen_panel.json',R127/'results/sem_native_v2/native_references.npz',R127/'results/sem_native_v2/native_SEM_objects.csv']
    freeze=dict(frozen_utc=now(),purpose='Four full planned research runs, no automatic model adoption',implementation_sha256={str(p):sha(p) for p in sources},required_records=[record(p) for p in records],python=sys.version,torch=torch.__version__,CUDA=torch.version.cuda,device=torch.cuda.get_device_name(0),platform=platform.platform(),free_bytes_before_training=shutil.disk_usage(ROOT).free,planned_runs=cfg['run_order'],planned_total_updates=32768,old_evidence_unchanged=True,real_holdout_claim=False)
    save(ROOT/'config/frozen_training.json',freeze);print(json.dumps(dict(frozen=True,protected_files=len(protected),planned_updates=32768)),flush=True)

if __name__=='__main__':main()
