"""One R129 continuation study with stop/resume and fixed real monitoring."""
import os,sys,time,argparse,traceback,socket,shutil
from runtime import *
from data import Bank
from engine import update,checkpoint,restore,evaluate_generated
from evaluate_real import evaluate as real_eval
import psutil
MODEL_NAME_BASE='R129_OpticalHybrid_LongTraining'

def acquire_lock(run):
    path=run/'active.lock'
    if path.exists():
        owner=load(path)
        if owner.get('host')==socket.gethostname() and psutil.pid_exists(owner['pid']):
            try:
                if abs(psutil.Process(owner['pid']).create_time()-owner['created'])<1:raise RuntimeError('This run is already active')
            except psutil.NoSuchProcess:pass
        elif owner.get('host')!=socket.gethostname():raise RuntimeError('Lock belongs to another host; verify that run is stopped before moving it')
        path.rename(run/('stale_lock_'+str(time.time_ns())+'.json'))
    save(path,dict(pid=os.getpid(),host=socket.gethostname(),created=psutil.Process().create_time()))
    return path

def train(name,resume=False,device='cuda',dry_run=False,stop_after=None):
    if not name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):raise ValueError('Use letters, numbers, underscore or hyphen for run name')
    cfg=load(ROOT/'config/training.json');bind=binding(cfg);verify_binding(bind)
    from verify_package import verify
    verify(full=False)
    if dry_run:
        m,opt=create(device);bank=Bank();b=bank.batch('train',0,device,0)
        from engine import objective
        m.eval()
        with torch.no_grad():loss,_=objective(m,b)
        print('Dry run OK',dict(device=device,input=list(b['source'].shape),loss=float(loss),planned_updates=cfg['updates'],parameters=sum(x.numel() for x in m.parameters())));return
    preflight=load(ROOT/'results/preflight/complete.json')
    if not preflight['passed'] or preflight['training_config_sha256']!=sha(ROOT/'config/training.json'):raise RuntimeError('Run preflight for this configuration before training')
    out=ROOT/'results/training'/name
    if out.exists() and not resume:raise FileExistsError('Run exists; choose Resume')
    if resume and not out.exists():raise FileNotFoundError('Run does not exist')
    out.mkdir(parents=True,exist_ok=resume);lock=acquire_lock(out)
    step=0;started=time.perf_counter();attempt=str(time.time_ns());log=out/f'updates_{attempt}.jsonl'
    try:
        model,opt=create(device);bank=Bank()
        if resume:
            latest=load(out/'latest_checkpoint.json');cp=ROOT/latest['path']
            if sha(cp)!=latest['sha256']:raise RuntimeError('Latest checkpoint hash mismatch')
            step=restore(cp,model,opt,bind)
            save(out/f'resume_{attempt}.json',dict(utc=now(),checkpoint=latest,restored_step=step,replayed_after_checkpoint_calls_are_not_additional_unique_updates=True))
        else:
            save(out/'run_plan.json',dict(MODEL_NAME_BASE=MODEL_NAME_BASE,config=cfg,binding=bind,started_utc=now(),initial_checkpoint=record(ROOT/'weights/initial_r129.pth')))
            cp=checkpoint(out,model,opt,step,bind);atomic(out/'latest_checkpoint.json',record(cp))
        def state(status,**extra):
            value=dict(model=MODEL_NAME_BASE,run=name,status=status,pid=os.getpid(),host=socket.gethostname(),completed_updates=step,planned_updates=cfg['updates'],epoch=step/cfg['splits']['train'],updated_utc=now(),attempt_seconds=time.perf_counter()-started,latest_checkpoint=load(out/'latest_checkpoint.json'),model_promoted=False,**extra)
            atomic(out/'status.json',value);atomic(ROOT/'results/active_training.json',value)
        def evaluate_current():
            folder=out/'evaluations'/f'step{step:05d}';folder.mkdir(parents=True,exist_ok=True)
            if step in cfg['dev_steps']:
                state('evaluating_development');evaluate_generated(model,bank,'dev',folder,step,device)
            if step in cfg['real_steps']:
                state('evaluating_real');real_eval(model,folder/'real',step,device)
            if step==cfg['updates']:
                state('evaluating_generated_test');evaluate_generated(model,bank,'test',folder,step,device)
        evaluate_current();state('training')
        with log.open('x',encoding='utf-8') as f:
            while step<cfg['updates']:
                if (out/'STOP_REQUESTED').exists():
                    cp=checkpoint(out,model,opt,step,bind);atomic(out/'latest_checkpoint.json',record(cp))
                    (out/'STOP_REQUESTED').rename(out/f'stop_consumed_{attempt}.txt');state('paused');return
                epoch,position=divmod(step,cfg['splits']['train']);index=int(bank.order(epoch)[position]);tick=time.perf_counter()
                batch=bank.batch('train',index,device,epoch);row=update(model,opt,batch,step+1,cfg);step+=1
                if device.startswith('cuda'):torch.cuda.synchronize()
                row.update(utc=now(),epoch=epoch,position=position,seconds=time.perf_counter()-tick)
                f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                if step%cfg['save_every']==0 or step in cfg['dev_steps'] or step in cfg['real_steps'] or step==cfg['updates'] or step==stop_after:
                    cp=checkpoint(out,model,opt,step,bind);atomic(out/'latest_checkpoint.json',record(cp));verify_binding(bind);evaluate_current()
                state('training',last_update=row)
                if step%16==0:print(f"{name}: {step}/{cfg['updates']} loss={row['loss']:.6f} seconds={row['seconds']:.2f}",flush=True)
                if step==stop_after:state('paused',reason='explicit bounded execution');return
                if step%128==0 and shutil.disk_usage(ROOT).free<10*2**30:raise RuntimeError('Less than 10 GiB free space; pause and inspect')
        required=[out/'evaluations'/f'step{s:05d}'/'dev.json' for s in cfg['dev_steps']]
        required += [out/'evaluations'/f'step{s:05d}'/'real/complete.json' for s in cfg['real_steps']]
        required += [out/'evaluations'/f'step{step:05d}'/'test.json',cp]
        if not all(p.is_file() for p in required):raise RuntimeError('Missing scheduled results; training is not complete')
        if not (out/'completion.json').exists():save(out/'completion.json',dict(completed_utc=now(),completed_updates=step,planned_updates=cfg['updates'],records=[record(p) for p in required],final_checkpoint=record(cp),model_promoted=False,default_inference_not_changed=True))
        state('complete')
    except BaseException:
        error=traceback.format_exc();save(out/f'failure_{attempt}.json',dict(utc=now(),step=step,error=error))
        try:state('failed',error=error)
        except Exception:pass
        raise
    finally:
        if lock.exists():lock.unlink()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',default='r129_long_01');p.add_argument('--resume',action='store_true');p.add_argument('--dry-run',action='store_true');p.add_argument('--device',default='cuda');p.add_argument('--stop-after',type=int);a=p.parse_args()
    train(a.run,a.resume,a.device,a.dry_run,a.stop_after)
