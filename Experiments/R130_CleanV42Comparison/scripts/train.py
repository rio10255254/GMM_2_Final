"""One fixed32-epoch V42 run; no R129 training or weight changes."""
import sys,time,argparse,traceback,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from common import *
from data_bank import Bank
from engine import update,checkpoint,restore,evaluate
from evaluate_real import evaluate as real_evaluate
MODEL_NAME_BASE='R130_CleanV42'
def main(resume=False):
    binding=verify_frozen();assert load(ROOT/'results/preflight/complete.json')['passed'];cfg=load(ROOT/'config/training.json');out=ROOT/'runs/v42_clean'
    if out.exists() and not resume:raise FileExistsError('Use --resume for the existing run')
    out.mkdir(exist_ok=resume);m,opt=create();bank=Bank();step=0;attempt=str(time.time_ns());start=time.perf_counter()
    if resume:
        latest=load(out/'latest.json');assert sha(latest['path'])==latest['sha256'];step=restore(latest['path'],m,opt,binding);save(out/f'resume_{attempt}.json',dict(utc=now(),checkpoint=latest,step=step))
    else:
        cp=checkpoint(out,m,opt,0,binding);atomic(out/'latest.json',record(cp));save(out/'started.json',dict(utc=now(),source=record(__file__),binding=binding,MODEL_NAME_BASE=MODEL_NAME_BASE,initial_digest=digest(m),pid=os.getpid()))
    def state(phase,**extra):
        value=dict(status=phase,pid=os.getpid(),step=step,updates=4096,epoch=step/128,epochs=32,updated_utc=now(),attempt_seconds=time.perf_counter()-start,latest=load(out/'latest.json'),**extra)
        atomic(out/'status.json',value);atomic(ROOT/'runs/launcher_logs/active_formal_run.json',value)
    def evaluations():
        epoch=step//128;folder=out/'evaluations'/f'epoch{epoch:02d}';folder.mkdir(parents=True,exist_ok=True)
        state('development');evaluate(m,bank,'dev',folder/'dev.json')
        if epoch in cfg['validation_epochs']:
            state('real_evaluation');real_evaluate(m,folder/'real',step)
        if step==4096:state('test_evaluation');evaluate(m,bank,'test',folder/'test.json')
    try:
        if step%128==0:evaluations()
        with (out/f'updates_{attempt}.jsonl').open('x',encoding='utf-8') as log:
            while step<4096:
                epoch,position=divmod(step,128);indices=bank.order(epoch)[position*4:(position+1)*4];tick=time.perf_counter()
                row=update(m,opt,bank.batch('train',indices,'cuda',epoch),step+1,cfg);step+=1;torch.cuda.synchronize();row.update(epoch=epoch,position=position,seconds=time.perf_counter()-tick,utc=now());log.write(json.dumps(row,allow_nan=False)+'\n');log.flush()
                if step%128==0:
                    cp=checkpoint(out,m,opt,step,binding);atomic(out/'latest.json',record(cp));verify_frozen();evaluations();print('Epoch',step//128,'/32','loss',row['loss'],flush=True)
                state('training',last_loss=row['loss'],last_update_seconds=row['seconds'])
                if shutil.disk_usage(ROOT).free<8*2**30:raise RuntimeError('Storage reserve reached')
        required=[out/'evaluations'/f'epoch{e:02d}'/'dev.json' for e in range(33)]
        required +=[out/'evaluations'/f'epoch{e:02d}'/'real/complete.json' for e in cfg['validation_epochs']]
        required +=[out/'evaluations/epoch32/test.json',cp]
        assert all(p.exists() for p in required)
        save(out/'completion.json',dict(completed_utc=now(),epochs=32,updates=4096,parent_pairs_seen=16384,records=[record(p) for p in required],checkpoint=record(cp),R129_unchanged=True,model_promoted=False));state('complete')
    except BaseException:
        save(out/f'failure_{attempt}.json',dict(utc=now(),step=step,error=traceback.format_exc()));state('failed');raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');a=p.parse_args();main(a.resume)
