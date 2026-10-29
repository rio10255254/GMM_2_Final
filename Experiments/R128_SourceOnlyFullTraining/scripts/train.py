"""One complete frozen run, with exact recoverable checkpoints and audits."""
import os,sys,time,json,argparse,traceback,shutil
from pathlib import Path
from common import *
sys.path.insert(0,str(ROOT))
import torch
from training.data import Bank
from training.engine import create,update,checkpoint,restore,state_digest
from evaluation.generated import evaluate as generated_eval
from evaluation.real import evaluate as real_eval
PROJECT_ROOT = Path(__file__).resolve().parents[3]

def verify_binding(binding):
    for p,h in binding['implementation_sha256'].items():
        if sha(p)!=h:raise RuntimeError(f'Frozen implementation changed: {p}')
    for item in binding['required_records']:
        if sha(str(PROJECT_ROOT / item['path']))!=item['sha256']:raise RuntimeError('Frozen input/decision record changed')
    if not load(ROOT/'results/data_audit.json')['passed'] or not load(ROOT/'results/engineering_preflight.json')['passed'] or not load(ROOT/'results/real_evaluator_preflight.json')['passed']:raise RuntimeError('Readiness failed')

def train(arm,seed,resume=False):
    cfg=load(ROOT/'config/study.json');frozen=load(ROOT/'config/frozen_training.json');verify_binding(frozen)
    binding={'frozen_training_sha256':sha(ROOT/'config/frozen_training.json')}
    if arm not in cfg['arms'] or seed not in cfg['model_seeds']:raise ValueError('Undeclared run')
    out=ROOT/'runs'/f'{arm}_s{seed}';existing=out.exists()
    if existing and not resume:raise FileExistsError('Existing run requires explicit resume')
    if resume and not existing:raise FileNotFoundError('No run to resume')
    out.mkdir(parents=True,exist_ok=resume);status=out/'status.json';bank=Bank();model,opt=create(seed,'cuda',cfg)
    start=time.perf_counter();step=0;attempt=now().replace(':','').replace('.','_');log=out/f'updates_{attempt}.jsonl'
    try:
        if resume:
            latest=load(out/'latest_checkpoint.json');cp=Path(latest['path'])
            if sha(cp)!=latest['sha256']:raise RuntimeError('Latest checkpoint changed')
            step=restore(cp,model,opt,binding,arm,seed)
            save(out/f'resume_{attempt}.json',dict(resumed_from=latest,step=step,previous_status=load(status),utc=now(),replayed_updates_are_not_new_unique_steps=True))
        else:
            # Same seed's image-only network is initialized independently per arm.
            cp=out/'checkpoints/step0000.pth';checkpoint(cp,model,opt,0,arm,seed,binding)
            initial=state_digest(model);expected=load(ROOT/'config/initial_states.json')[str(seed)]
            if initial!=expected['parameter_sha256']:raise RuntimeError('Unmatched initial state')
            if torch.count_nonzero(model.prior.head.weight) or torch.count_nonzero(model.prior.head.bias):raise RuntimeError('Initial equivalence invalid')
            atomic(out/'latest_checkpoint.json',record(cp))
        def state(phase,**extra):
            atomic(status,dict(run=f'{arm}_s{seed}',arm=arm,seed=seed,status=phase,pid=os.getpid(),completed_updates=step,planned_updates=cfg['updates_per_run'],unique_updates_definition='Current exact checkpoint continuation; replayed calls are retained separately',latest_checkpoint=load(out/'latest_checkpoint.json'),seconds_this_attempt=time.perf_counter()-start,updated_utc=now(),model_promoted=False,**extra))
        def evaluations(current_cp):
            verify_binding(frozen)
            if step in cfg['dev_checkpoints']:
                state('evaluating_generated_dev')
                generated_eval(model,bank,'dev',step,out/'evaluations'/f'dev_step{step:04d}.json',record(current_cp))
            if step in cfg['real_checkpoints']:
                state('evaluating_real_microscopy_and_SEM')
                if step==0:
                    # Shared exact Raw baseline is independently bound to every
                    # equal-output initialization; no fabricated per-run result.
                    baseline=load(ROOT/'results/real_baseline/verification.json')
                    if not baseline['neutral_Raw_equivalence_used']:raise RuntimeError('Wrong baseline')
                    p=out/'evaluations/real_step0000_equivalence.json'
                    if not p.exists():save(p,dict(checkpoint=record(current_cp),common_real_baseline=record(ROOT/'results/real_baseline/verification.json'),proof='Zero last layer gives zero each of four updates for all finite image inputs; tested at each seed plus full evaluator integration',initial_parameter_sha256=state_digest(model)))
                else:real_eval(model,out/'evaluations'/f'real_step{step:04d}',record(current_cp))
            if step in cfg['final_generated_test_checkpoints']:
                state('evaluating_final_generated_test')
                generated_eval(model,bank,'test',step,out/'evaluations'/f'test_step{step:04d}.json',record(current_cp))
        evaluations(cp);state('training')
        with log.open('x',encoding='utf-8') as f:
            while step<cfg['updates_per_run']:
                epoch=step//cfg['splits']['train'];position=step%cfg['splits']['train'];index=int(bank.order(epoch)[position])
                tick=time.perf_counter();batch=bank.batch('train',index,'cuda',epoch)
                row=update(model,opt,batch,step+1,arm,cfg);step+=1
                torch.cuda.synchronize();row.update(epoch=epoch,position=position,utc=now(),seconds=time.perf_counter()-tick)
                f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                if step%cfg['save_every_updates']==0 or step in cfg['dev_checkpoints'] or step in cfg['real_checkpoints'] or step==cfg['updates_per_run']:
                    cp=out/'checkpoints'/f'step{step:04d}.pth'
                    checkpoint(cp,model,opt,step,arm,seed,binding);atomic(out/'latest_checkpoint.json',record(cp))
                    evaluations(cp)
                state('training',last_update=row)
                if step%32==0:print(json.dumps(dict(arm=arm,seed=seed,step=step,loss=row['loss'],update_seconds=row['seconds'])),flush=True)
                if step%128==0 and shutil.disk_usage(ROOT).free<10*2**30:raise RuntimeError('Storage reserve reached')
        verify_binding(frozen)
        required=[out/'evaluations'/f'dev_step{s:04d}.json' for s in cfg['dev_checkpoints']]
        required += [out/'evaluations'/f'real_step{s:04d}'/'verification.json' for s in cfg['real_checkpoints'] if s]
        required += [out/'evaluations/real_step0000_equivalence.json',out/'evaluations'/f'test_step{step:04d}.json',cp]
        if not all(p.is_file() for p in required):raise RuntimeError('Missing scheduled result')
        save(out/'completion.json',dict(run=f'{arm}_s{seed}',completed_updates=step,planned_updates=cfg['updates_per_run'],finished_utc=now(),records=[record(p) for p in required],final_parameter_sha256=state_digest(model),model_promoted=False,physical_accuracy_qualified=False))
        state('complete')
    except BaseException:
        atomic(status,dict(run=f'{arm}_s{seed}',status='failed',pid=os.getpid(),completed_updates=step,planned_updates=cfg['updates_per_run'],error=traceback.format_exc(),updated_utc=now(),model_promoted=False))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=['I','P'],required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args();train(a.arm,a.seed,a.resume)
